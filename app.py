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
def rand_msg():
    category = random.choice(["duas", "adhkar", "hadiths"])
    return random.choice(content[category])

def send_random_message():
    message = rand_msg()
    for uid in target_users:
        if uid not in notifications_off:
            try:
                line_bot_api.push_message(uid, TextSendMessage(text=message))
            except:
                pass
    for gid in target_groups:
        if gid not in notifications_off:
            try:
                line_bot_api.push_message(gid, TextSendMessage(text=message))
            except:
                pass

def message_loop():
    while True:
        send_random_message()
        time.sleep(random.randint(3600,5400))  # بين ساعة و1.5 ساعة

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
        if user_id not in links_count:
            links_count[user_id] = 1
        else:
            links_count[user_id] += 1
        if links_count[user_id] >= 2:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
        return True
    return False

# ---------------- تسبيح ---------------- #
tasbih_limits = 33
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0}

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # تسجيل المستخدمين والقروبات لأول مرة
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
    ensure_user_counts(user_id)

    # إرسال رسالة عشوائية عند أول تواصل تلقائي
    if first_time and target_id not in notifications_off:
        message = rand_msg()
        for uid in target_users:
            if uid not in notifications_off:
                try:
                    line_bot_api.push_message(uid, TextSendMessage(text=message))
                except:
                    pass
        for gid in target_groups:
            if gid not in notifications_off:
                try:
                    line_bot_api.push_message(gid, TextSendMessage(text=message))
                except:
                    pass

    # حماية الروابط
    if handle_links(event, user_id):
        return

    # أوامر محددة
    if user_text.lower() == "مساعدة":
        help_text = """أوامر البوت المتاحة:

1. ذكرني
   - يرسل دعاء أو حديث أو ذكر عشوائي لجميع المستخدمين.

2. تسبيح
   - عرض عدد التسبيحات لكل كلمة لكل مستخدم.

3. سبحان الله / الحمد لله / الله أكبر
   - زيادة عدد التسبيحات لكل كلمة.

4. الإشعارات:
   - إيقاف: يوقف الإشعارات التلقائية.
   - تشغيل: يعيد تفعيل الإشعارات التلقائية.
"""
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if user_text.lower() == "ذكرني":
        message = rand_msg()
        for uid in target_users:
            if uid not in notifications_off:
                try:
                    line_bot_api.push_message(uid, TextSendMessage(text=message))
                except:
                    pass
        for gid in target_groups:
            if gid not in notifications_off:
                try:
                    line_bot_api.push_message(gid, TextSendMessage(text=message))
                except:
                    pass
        return

    if user_text.lower() == "تسبيح":
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        tasbih_counts[user_id][user_text] += 1
        save_data()
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text.lower() == "إيقاف":
        notifications_off.add(target_id)
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف الإشعارات التلقائية"))
        return

    if user_text.lower() == "تشغيل":
        if target_id in notifications_off:
            notifications_off.remove(target_id)
            save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إعادة تفعيل الإشعارات التلقائية"))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
