from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time
from dotenv import load_dotenv

# ---------------- إعداد البوت ---------------- #
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- ملفات البيانات ---------------- #
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": [], "groups": [], "tasbih": {}, "notifications_off": []}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}, set()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("groups", [])), set(data.get("users", [])), data.get("tasbih", {}), set(data.get("notifications_off", []))

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "groups": list(target_groups),
            "users": list(target_users),
            "tasbih": tasbih_counts,
            "notifications_off": list(notifications_off)
        }, f, ensure_ascii=False, indent=2)

target_groups, target_users, tasbih_counts, notifications_off = load_data()

# ---------------- تحميل المحتوى ---------------- #
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# ---------------- إرسال رسائل عشوائية ---------------- #
def send_random_message():
    category = random.choice(["duas", "adhkar", "hadiths"])
    message = random.choice(content[category])
    all_ids = list(target_groups) + list(target_users)
    for tid in all_ids:
        if tid not in notifications_off:
            try:
                line_bot_api.push_message(tid, TextSendMessage(text=message))
            except:
                pass

def message_loop():
    while True:
        send_random_message()
        time.sleep(random.randint(3600, 5400))  # من ساعة إلى ساعة ونصف

threading.Thread(target=message_loop, daemon=True).start()

# ---------------- Webhook ---------------- #
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

# ---------------- حماية الروابط ---------------- #
links_count = {}
def handle_links(event, user_id):
    text = event.message.text.strip()
    if "http://" in text or "https://" in text or "www." in text:
        links_count[user_id] = links_count.get(user_id, 0) + 1
        if links_count[user_id] >= 2:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
        return True
    return False

# ---------------- تسبيح ---------------- #
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # تحديد معرف الهدف (قروب أو مستخدم)
    if hasattr(event.source, "group_id") and event.source.group_id:
        target_id = event.source.group_id
    else:
        target_id = user_id

    # تسجيل المستخدم/القروب إذا جديد
    if target_id not in target_groups and target_id not in target_users:
        if hasattr(event.source, "group_id") and event.source.group_id:
            target_groups.add(target_id)
        else:
            target_users.add(target_id)
        save_data()
        if target_id not in notifications_off:
            category = random.choice(["duas", "adhkar", "hadiths"])
            message = random.choice(content[category])
            line_bot_api.push_message(target_id, TextSendMessage(text=message))

    ensure_user_counts(user_id)

    # حماية الروابط
    if handle_links(event, user_id):
        return

    # الأوامر
    if user_text == "مساعدة":
        help_text = """اوامر البوت:

1. ذكرني  
   يرسل دعاء او حديث او ذكر عشوائي للجميع

2. تسبيح  
   يعرض عدد التسبيحات الحالية

3. سبحان الله / الحمد لله / الله أكبر  
   يزيد العداد

4. ايقاف  
   يوقف الاذكار التلقائية

5. تشغيل  
   يعيد تشغيل الاذكار التلقائية
"""
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if user_text == "ذكرني":
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content[category])
        for tid in list(target_groups) + list(target_users):
            if tid not in notifications_off:
                try:
                    line_bot_api.push_message(tid, TextSendMessage(text=message))
                except:
                    pass
        return

    if user_text == "تسبيح":
        counts = tasbih_counts[user_id]
        status = f"تسبيحك:\nسبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        tasbih_counts[user_id][user_text] += 1
        save_data()
        counts = tasbih_counts[user_id]
        status = f"تسبيحك:\nسبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text == "ايقاف":
        notifications_off.add(target_id)
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم ايقاف الاشعارات التلقائية"))
        return

    if user_text == "تشغيل":
        notifications_off.discard(target_id)
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم اعادة تشغيل الاشعارات التلقائية"))
        return

# ---------------- تشغيل ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
