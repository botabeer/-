from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json
from dotenv import load_dotenv

# إعداد البوت
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ملفات البيانات
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": [], "groups": [], "notifications_off": []}, f, ensure_ascii=False, indent=2)
        return set(), set(), set()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("groups", [])), set(data.get("users", [])), set(data.get("notifications_off", []))

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "groups": list(target_groups),
            "users": list(target_users),
            "notifications_off": list(notifications_off)
        }, f, ensure_ascii=False, indent=2)

target_groups, target_users, notifications_off = load_data()

# تحميل المحتوى
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# Webhook
@app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("خطأ في التوقيع")
    return "OK", 200

# التعامل مع الرسائل
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # تسجيل المستخدم أو القروب لأول مرة
    first_time = False
    if hasattr(event.source, 'group_id') and event.source.group_id:
        target_id = event.source.group_id
        if target_id not in target_groups:
            first_time = True
        target_groups.add(target_id)
    else:
        target_id = user_id
        if target_id not in target_users:
            first_time = True
        target_users.add(target_id)

    save_data()

    # عند أول رسالة لأي مستخدم أو قروب: إرسال ذكر لجميع المسجلين
    if first_time:
        all_ids = list(target_groups) + list(target_users)
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content[category])
        for tid in all_ids:
            if tid not in notifications_off:
                try:
                    line_bot_api.push_message(tid, TextSendMessage(text=message))
                except:
                    pass

    # أمر "ذكرني" يرسل للجميع
    if user_text.lower() == "ذكرني":
        all_ids = list(target_groups) + list(target_users)
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content[category])
        for tid in all_ids:
            if tid not in notifications_off:
                try:
                    line_bot_api.push_message(tid, TextSendMessage(text=message))
                except:
                    pass
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
