from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time
from dotenv import load_dotenv
from datetime import datetime

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
HELP_FILE = "help.txt"  # ملف المساعدة الخارجي

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
tasbih_words = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله"]

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {word: 0 for word in tasbih_words}

# ---------------- إعادة ضبط التسبيح يوميًا ---------------- #
last_reset_date = datetime.now().date()

def reset_tasbih_daily():
    global last_reset_date
    while True:
        now = datetime.now()
        if now.date() != last_reset_date:
            for uid in tasbih_counts:
                for word in tasbih_words:
                    tasbih_counts[uid][word] = 0
            save_data()
            last_reset_date = now.date()
        time.sleep(60)  # تحقق كل دقيقة

threading.Thread(target=reset_tasbih_daily, daemon=True).start()

# ---------------- إرسال أذكار وتسبيح تلقائي ---------------- #
def send_random_message():
    category = random.choice(["duas", "adhkar", "hadiths"])
    message = random.choice(content.get(category, ["لا يوجد محتوى"]))
    if random.random() < 0.5:
        message += "\n" + "استغفر الله"

    all_ids = list(target_users) + list(target_groups)
    for tid in all_ids:
        if tid not in notifications_off:
            try:
                line_bot_api.push_message(tid, TextSendMessage(text=message))
            except:
                pass

def message_loop():
    while True:
        send_random_message()
        time.sleep(random.randint(3600, 5400))

threading.Thread(target=message_loop, daemon=True).start()

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

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    gid = getattr(event.source, 'group_id', None)

    first_time = False
    if user_id not in target_users:
        target_users.add(user_id)
        first_time = True
    if gid and gid not in target_groups:
        target_groups.add(gid)
        first_time = True
    save_data()
    ensure_user_counts(user_id)

    if first_time:
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content.get(category, ["لا يوجد محتوى"]))
        if random.random() < 0.5:
            message += "\n" + "استغفر الله"
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=message))
        except:
            pass
        if gid:
            try:
                line_bot_api.push_message(gid, TextSendMessage(text=message))
            except:
                pass
        return

    if handle_links(event, user_id):
        return

    # ---------------- قراءة المساعدة من ملف خارجي ---------------- #
    if user_text.lower() == "مساعدة":
        try:
            with open(HELP_FILE, "r", encoding="utf-8") as f:
                help_text = f.read()
        except:
            help_text = "لا يوجد محتوى مساعدة حالياً."
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if user_text.lower() == "تسبيح":
        counts = tasbih_counts[user_id]
        status = "\n".join([f"{word}: {counts[word]}/{tasbih_limits}" for word in tasbih_words])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in tasbih_words:
        if tasbih_counts[user_id][user_text] < tasbih_limits:
            tasbih_counts[user_id][user_text] += 1
            save_data()
        counts = tasbih_counts[user_id]
        status = "\n".join([f"{word}: {counts[word]}/{tasbih_limits}" for word in tasbih_words])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text.lower() == "إيقاف":
        target_id = gid if gid else user_id
        notifications_off.add(target_id)
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف الإشعارات التلقائية"))
        return

    if user_text.lower() == "تشغيل":
        target_id = gid if gid else user_id
        if target_id in notifications_off:
            notifications_off.remove(target_id)
            save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إعادة تفعيل الإشعارات التلقائية"))
        return

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
