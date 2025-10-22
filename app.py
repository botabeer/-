from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, time
from dotenv import load_dotenv
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

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
HELP_FILE = "help.txt"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": [], "groups": [], "tasbih": {}, "notifications_off": []}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}, set()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("users", [])), set(data.get("groups", [])), data.get("tasbih", {}), set(data.get("notifications_off", []))

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": list(target_users),
            "groups": list(target_groups),
            "tasbih": tasbih_counts,
            "notifications_off": list(notifications_off)
        }, f, ensure_ascii=False, indent=2)

target_users, target_groups, tasbih_counts, notifications_off = load_data()

# ---------------- تحميل المحتوى ---------------- #
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# ---------------- تسبيح ---------------- #
tasbih_limits = 33
tasbih_map = {
    "سبحان الله": "سبحان الله",
    "سبحانالله": "سبحان الله",
    "الحمد لله": "الحمد لله",
    "الحمدلله": "الحمد لله",
    "الله أكبر": "الله أكبر",
    "اللهاكبر": "الله أكبر",
    "استغفر الله": "استغفر الله",
    "استغفرالله": "استغفر الله"
}
tasbih_words = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله"]

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {word: 0 for word in tasbih_words}

# ---------------- إعادة ضبط التسبيح يوميًا ---------------- #
last_reset_date = datetime.now().date()
def reset_tasbih_daily():
    global last_reset_date
    now = datetime.now()
    if now.date() != last_reset_date:
        for uid in tasbih_counts:
            for word in tasbih_words:
                tasbih_counts[uid][word] = 0
        save_data()
        last_reset_date = now.date()

# ---------------- إرسال أذكار ودعاء تلقائي ---------------- #
def send_random_message():
    all_ids = list(target_users) + list(target_groups)
    message = random.choice(content.get("duas", ["لا يوجد محتوى"]))
    if random.random() < 0.5:
        message += "\nاستغفر الله"
    for tid in all_ids:
        if tid not in notifications_off:
            try:
                line_bot_api.push_message(tid, TextSendMessage(text=message))
            except:
                pass

# ---------------- جدولة APScheduler ---------------- #
scheduler = BackgroundScheduler()
scheduler.add_job(reset_tasbih_daily, 'interval', minutes=1)
scheduler.add_job(send_random_message, 'interval', seconds=random.randint(3600, 5400))
scheduler.start()

# ---------------- حماية الروابط ---------------- #
links_count = {}
def handle_links(event, user_id):
    text = event.message.text.strip()
    if "http://" in text or "https://" in text or "www." in text:
        links_count[user_id] = links_count.get(user_id, 0) + 1
        if links_count[user_id] >= 2:
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
            except:
                pass
        return True
    return False

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
        pass
    return "OK", 200

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    gid = getattr(event.source, 'group_id', None)

    first_time = False

    # تسجيل المستخدم والقروب عند أول رسالة
    if user_id not in target_users:
        target_users.add(user_id)
        first_time = True
    if gid and gid not in target_groups:
        target_groups.add(gid)
        first_time = True

    save_data()
    ensure_user_counts(user_id)

    # حماية الروابط
    if handle_links(event, user_id):
        return

    # دالة إرسال ذكر أو دعاء
    def send_test_message(tid):
        message = random.choice(content.get("duas", ["لا يوجد محتوى"]))
        if random.random() < 0.5:
            message += "\nاستغفر الله"
        try:
            line_bot_api.push_message(tid, TextSendMessage(text=message))
        except:
            pass

    # أول رسالة → إرسال ذكر أو دعاء للمستخدم والقروب
    if first_time:
        send_test_message(user_id)
        if gid:
            send_test_message(gid)

    # أمر "ذكرني" → إرسال ذكر أو دعاء لجميع المستخدمين والقروبات
    if user_text.lower() == "ذكرني":
        for tid in list(target_users) + list(target_groups):
            if tid not in notifications_off:
                send_test_message(tid)
        return

    # أمر المساعدة
    if user_text.lower() == "مساعدة":
        try:
            with open(HELP_FILE, "r", encoding="utf-8") as f:
                help_text = f.read()
        except:
            help_text = "لا يوجد محتوى مساعدة حالياً."
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        except:
            pass
        return

    # عرض التسبيح
    if user_text.lower() == "تسبيح":
        counts = tasbih_counts[user_id]
        status = "\n".join([f"{word}: {counts[word]}/{tasbih_limits}" for word in tasbih_words])
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except:
            pass
        return

    # زيادة التسبيح
    key = tasbih_map.get(user_text)
    if key:
        if tasbih_counts[user_id][key] < tasbih_limits:
            tasbih_counts[user_id][key] += 1
            save_data()
        counts = tasbih_counts[user_id]
        status = "\n".join([f"{word}: {counts[word]}/{tasbih_limits}" for word in tasbih_words])
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except:
            pass
        return

    # إيقاف الإشعارات
    if user_text.lower() == "إيقاف":
        target_id = gid if gid else user_id
        notifications_off.add(target_id)
        save_data()
        return

    # إعادة تشغيل الإشعارات
    if user_text.lower() == "تشغيل":
        target_id = gid if gid else user_id
        if target_id in notifications_off:
            notifications_off.remove(target_id)
            save_data()
        return

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
