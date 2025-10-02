from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, json, random, threading, time

app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# تحميل المحتوى
with open("content.json", "r", encoding="utf-8") as f:
    content = json.load(f)

# تحميل بيانات المستخدمين والمجموعات
DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"users": [], "groups": [], "notify": {}}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# وظيفة إرسال الرسائل التلقائية لجميع المستخدمين والمجموعات
def send_auto_messages():
    while True:
        for target_id in data["notify"]:
            if data["notify"][target_id]:
                message = random.choice(content["duas"] + content["adhkar"] + content["hadiths"])
                try:
                    line_bot_api.push_message(target_id, TextSendMessage(text=message))
                except:
                    pass
        time.sleep(random.randint(3600, 7200))  # بين 1 و 2 ساعة بشكل عشوائي

threading.Thread(target=send_auto_messages, daemon=True).start()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", None)
    target_id = group_id if group_id else user_id

    # تسجيل المعرفات
    if group_id:
        if group_id not in data["groups"]:
            data["groups"].append(group_id)
    else:
        if user_id not in data["users"]:
            data["users"].append(user_id)
    if target_id not in data["notify"]:
        data["notify"][target_id] = True
    save_data()

    # أوامر المستخدم
    if text.lower() == "مساعدة":
        help_text = """أوامر البوت:
1. ذكرني - يرسل لك دعاء/حديث/ذكر عشوائي
2. إيقاف - يوقف الإشعارات التلقائية
3. تشغيل - يعيد تفعيل الإشعارات التلقائية
"""
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if text.lower() == "ذكرني" and data["notify"].get(target_id, True):
        message = random.choice(content["duas"] + content["adhkar"] + content["hadiths"])
        line_bot_api.push_message(target_id, TextSendMessage(text=message))
        return

    if text.lower() == "إيقاف":
        data["notify"][target_id] = False
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف الإشعارات التلقائية"))
        return

    if text.lower() == "تشغيل":
        data["notify"][target_id] = True
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تفعيل الإشعارات التلقائية"))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
