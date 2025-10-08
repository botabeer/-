from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

DATA_FILE = "data.json"
CONTENT_FILE = "content.json"

# تحميل البيانات أو إنشاء ملف جديد
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

# تحميل المحتوى (الأذكار والأدعية)
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

@app.route("/", methods=["GET"])
def home():
    return "Bot is running ✅", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ خطأ في التوقيع")
        return "Invalid signature", 400
    return "OK", 200


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # تحديد نوع المصدر (خاص أو قروب)
    group_id = getattr(event.source, 'group_id', None)
    target_id = group_id if group_id else user_id

    first_time = False

    # تسجيل أول مرة
    if group_id:
        if group_id not in target_groups:
            target_groups.add(group_id)
            first_time = True
    else:
        if user_id not in target_users:
            target_users.add(user_id)
            first_time = True

    # حفظ البيانات
    save_data()

    # إرسال ذكر عشوائي عند أول رسالة
    if first_time:
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content[category])

        try:
            line_bot_api.push_message(target_id, TextSendMessage(text=message))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تفعيل التذكير 🌿"))
        except Exception as e:
            print(f"❌ خطأ أثناء الإرسال: {e}")
        return

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
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📩 تم إرسال ذكر للجميع."))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
