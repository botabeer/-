from flask import Flask, request, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, 
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
import os, threading, logging, json, time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

if not ACCESS_TOKEN or not SECRET:
    raise ValueError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

DATA_FILE = "data/data.json"
TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]

def load_json(file, default):
    if not os.path.exists(file):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"tasbih": tasbih_counts}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ حفظ: {e}")

data = load_json(DATA_FILE, {"tasbih": {}})
tasbih_counts = data.get("tasbih", {})

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        save_data()

def send_message(target_id, message):
    def send_async():
        try:
            with ApiClient(configuration) as api_client:
                api = MessagingApi(api_client)
                if isinstance(message, str):
                    api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=message)]))
                else:
                    api.push_message(PushMessageRequest(to=target_id, messages=[message]))
        except Exception as e:
            logger.error(f"ارسال فشل {target_id}: {e}")
    threading.Thread(target=send_async, daemon=True).start()

def reply_message(reply_token, message):
    def send_reply():
        try:
            with ApiClient(configuration) as api_client:
                api = MessagingApi(api_client)
                if isinstance(message, str):
                    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)]))
                else:
                    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]))
        except Exception as e:
            logger.error(f"رد فشل: {e}")
    threading.Thread(target=send_reply, daemon=True).start()

def create_buttons_only_tasbih_flex(user_id):
    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "بوت 85",
                    "size": "md",
                    "weight": "bold",
                    "color": "#ffffff",
                    "align": "center"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "استغفر الله",
                                "data": f"tasbih_استغفر الله_{user_id}"
                            },
                            "style": "secondary",
                            "color": "#404040",
                            "height": "sm"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "سبحان الله",
                                "data": f"tasbih_سبحان الله_{user_id}"
                            },
                            "style": "secondary",
                            "color": "#404040",
                            "height": "sm"
                        }
                    ],
                    "spacing": "xs",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "الحمد لله",
                                "data": f"tasbih_الحمد لله_{user_id}"
                            },
                            "style": "secondary",
                            "color": "#404040",
                            "height": "sm"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "الله أكبر",
                                "data": f"tasbih_الله أكبر_{user_id}"
                            },
                            "style": "secondary",
                            "color": "#404040",
                            "height": "sm"
                        }
                    ],
                    "spacing": "xs",
                    "margin": "xs"
                },
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#404040"
                },
                {
                    "type": "text",
                    "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري @ 2025",
                    "size": "xxs",
                    "color": "#aaaaaa",
                    "align": "center",
                    "margin": "sm"
                }
            ],
            "paddingAll": "12px",
            "backgroundColor": "#1a1a1a"
        }
    }
    return FlexMessage(alt_text="التسبيح", contents=FlexContainer.from_dict(flex_content))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip().lower()
    user_id = event.source.user_id

    ensure_user_counts(user_id)

    if user_text == "تسبيح":
        flex_msg = create_buttons_only_tasbih_flex(user_id)
        reply_message(event.reply_token, flex_msg)
    elif user_text == "مساعدة":
        reply_message(event.reply_token, "أرسل 'تسبيح' لفتح نافذة التسبيح التفاعلية.")

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data.startswith("tasbih_"):
        parts = data.replace("tasbih_", "").rsplit("_", 1)
        if len(parts) != 2:
            return
        tasbih_text, user_id = parts
        ensure_user_counts(user_id)
        if tasbih_text in TASBIH_KEYS:
            tasbih_counts[user_id][tasbih_text] += 1
            save_data()
            reply_message(event.reply_token, f"{tasbih_text} تم")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
