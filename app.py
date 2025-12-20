import os, json, threading, logging, random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, PostbackEvent, FlexSendMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

# ==== ملفات البيانات ====
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
FADL_FILE = "data/fadl.json"
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
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==== تحميل البيانات ====
data = load_json(DATA_FILE, {"groups": [], "users": [], "tasbih": {}})
target_groups = set(data.get("groups", []))
target_users = set(data.get("users", []))
tasbih_counts = data.get("tasbih", {})

content = load_json(CONTENT_FILE, {"duas": [], "adhkar": [], "hadiths": [], "quran": []})
fadl_content = load_json(FADL_FILE, {"fadl": []}).get("fadl", [])
fadl_index = 0

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        save_all()

def save_all():
    data["groups"] = list(target_groups)
    data["users"] = list(target_users)
    data["tasbih"] = tasbih_counts
    save_data()

def send_message(target_id, message):
    def send_async():
        try:
            if isinstance(message, str):
                line_bot_api.push_message(target_id, TextSendMessage(text=message))
            else:
                line_bot_api.push_message(target_id, message)
        except Exception as e:
            logger.error(f"ارسال فشل {target_id}: {e}")
    threading.Thread(target=send_async, daemon=True).start()

def reply_message(reply_token, message):
    def send_reply():
        try:
            if isinstance(message, str):
                line_bot_api.reply_message(reply_token, TextSendMessage(text=message))
            else:
                line_bot_api.reply_message(reply_token, message)
        except Exception as e:
            logger.error(f"رد فشل: {e}")
    threading.Thread(target=send_reply, daemon=True).start()

# ==== نافذة التسبيح بالأزرار ====
def create_tasbih_flex(user_id):
    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "بوت 85", "size": "md", "weight": "bold", "color": "#ffffff", "align": "center"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "postback", "label": "استغفر الله", "data": f"tasbih_استغفر الله_{user_id}"}, "style": "secondary", "color": "#404040", "height": "sm"},
                        {"type": "button", "action": {"type": "postback", "label": "سبحان الله", "data": f"tasbih_سبحان الله_{user_id}"}, "style": "secondary", "color": "#404040", "height": "sm"}
                    ],
                    "spacing": "xs",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "postback", "label": "الحمد لله", "data": f"tasbih_الحمد لله_{user_id}"}, "style": "secondary", "color": "#404040", "height": "sm"},
                        {"type": "button", "action": {"type": "postback", "label": "الله أكبر", "data": f"tasbih_الله أكبر_{user_id}"}, "style": "secondary", "color": "#404040", "height": "sm"}
                    ],
                    "spacing": "xs",
                    "margin": "xs"
                },
                {"type": "separator", "margin": "md", "color": "#404040"},
                {"type": "text", "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري @ 2025", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "sm"}
            ],
            "paddingAll": "12px",
            "backgroundColor": "#1a1a1a"
        }
    }
    return FlexSendMessage(alt_text="التسبيح", contents=flex_content)

def get_next_fadl():
    global fadl_index
    if not fadl_content:
        return "لا يوجد فضل متاح"
    msg = fadl_content[fadl_index]
    fadl_index = (fadl_index + 1) % len(fadl_content)
    return msg

# ==== التعامل مع الرسائل ====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    lower_text = user_text.lower()
    user_id = event.source.user_id
    gid = getattr(event.source, "group_id", None)

    if gid:
        target_groups.add(gid)
    else:
        target_users.add(user_id)

    ensure_user_counts(user_id)

    if lower_text == "تسبيح":
        flex_msg = create_tasbih_flex(user_id)
        reply_message(event.reply_token, flex_msg)

    elif lower_text == "ذكرني":
        try:
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if not messages:
                reply_message(event.reply_token, "لا يوجد محتوى متاح حالياً")
                return
            message = random.choice(messages)
            reply_message(event.reply_token, message)
            for g in target_groups:
                send_message(g, message)
            for u in target_users:
                if u != user_id:
                    send_message(u, message)
        except Exception as e:
            logger.error(f"خطأ أمر ذكرني: {e}")

    elif lower_text == "فضل":
        reply_message(event.reply_token, get_next_fadl())

    elif lower_text == "مساعدة":
        reply_message(event.reply_token, "أوامر البوت:\n- تسبيح\n- ذكرني\n- فضل")

    save_all()

# ==== التعامل مع الضغط على الأزرار ====
@handler.add(PostbackEvent)
def handle_postback(event):
    data_post = event.postback.data
    if data_post.startswith("tasbih_"):
        parts = data_post.replace("tasbih_", "").rsplit("_", 1)
        if len(parts) != 2:
            return
        tasbih_text, user_id = parts
        ensure_user_counts(user_id)
        if tasbih_text in TASBIH_KEYS:
            tasbih_counts[user_id][tasbih_text] += 1
            reply_message(event.reply_token, f"{tasbih_text} ({tasbih_counts[user_id][tasbih_text]}/33)")
            save_all()

# ==== Webhook endpoint ====
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
    logger.info(f"بوت 85 يعمل على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
