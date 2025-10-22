from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, json, threading, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import random

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

# ---------------- إرسال ذكر/دعاء ---------------- #
def send_random_message(to_ids=None):
    category = random.choice(["duas", "adhkar", "hadiths"])
    message = random.choice(content.get(category, ["لا يوجد محتوى"]))
    if to_ids is None:
        all_ids = list(target_users) + list(target_groups)
    else:
        all_ids = to_ids
    for tid in all_ids:
        if tid not in notifications_off:
            try:
                line_bot_api.push_message(tid, TextSendMessage(text=message))
            except:
                pass

# ---------------- التذكير التلقائي 5 مرات يوميًا ---------------- #
def daily_reminder_loop():
    reminder_hours = [9, 12, 15, 18, 21]  # أوقات التذكير
    while True:
        now = datetime.now()
        for hour in reminder_hours:
            target_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target_time < now:
                target_time += timedelta(days=1)
            seconds_until = (target_time - datetime.now()).total_seconds()
            time.sleep(seconds_until)
            send_random_message()
        now = datetime.now()

threading.Thread(target=daily_reminder_loop, daemon=True).start()

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

# ---------------- التسبيح ---------------- #
tasbih_limits = 33
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0, "استغفر الله":0}

def normalize_tasbih(text):
    mapping = {
        "سبحان الله": "سبحان الله",
        "الحمد لله": "الحمد لله",
        "الله أكبر": "الله أكبر",
        "استغفر الله": "استغفر الله",
        "استغفرالله": "استغفر الله"
    }
    return mapping.get(text.replace(" ", ""), None)

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    gid = getattr(event.source, 'group_id', None)

    # ---------------- تسجيل المستخدمين والقروبات تلقائي ---------------- #
    first_time = False
    if user_id not in target_users:
        target_users.add(user_id)
        first_time = True
    if gid and gid not in target_groups:
        target_groups.add(gid)
        first_time = True
    save_data()
    ensure_user_counts(user_id)

    # ---------------- إرسال ذكر/دعاء بعد التسجيل ---------------- #
    if first_time:
        send_random_message(to_ids=[user_id] + ([gid] if gid else []))

    # ---------------- حماية الروابط ---------------- #
    if handle_links(event, user_id):
        return

    # ---------------- أوامر المساعدة ---------------- #
    if user_text.lower() == "مساعدة":
        try:
            with open("help.txt", "r", encoding="utf-8") as f:
                help_text = f.read()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        except:
            pass
        return

    # ---------------- عرض التسبيح ---------------- #
    if user_text.lower() == "تسبيح":
        counts = tasbih_counts[user_id]
        status = "\n".join([f"{k}: {v}/{tasbih_limits}" for k,v in counts.items()])
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except:
            pass
        return

    # ---------------- التسبيح (زيادة العد) ---------------- #
    tasbih_key = normalize_tasbih(user_text)
    if tasbih_key:
        if tasbih_counts[user_id][tasbih_key] < tasbih_limits:
            tasbih_counts[user_id][tasbih_key] += 1
        save_data()
        counts = tasbih_counts[user_id]
        status = "\n".join([f"{k}: {v}/{tasbih_limits}" for k,v in counts.items()])
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except:
            pass
        return

    # ---------------- أمر ذكرني ---------------- #
    if user_text.lower() == "ذكرني":
        send_random_message()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إرسال الذكر لجميع المستخدمين والقروبات"))
        except:
            pass
        return

    # ---------------- إيقاف التذكير ---------------- #
    if user_text.lower() == "إيقاف":
        target_id = gid if gid else user_id
        notifications_off.add(target_id)
        save_data()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف الإشعارات التلقائية"))
        except:
            pass
        return

    # ---------------- تشغيل التذكير ---------------- #
    if user_text.lower() == "تشغيل":
        target_id = gid if gid else user_id
        if target_id in notifications_off:
            notifications_off.remove(target_id)
            save_data()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إعادة تفعيل الإشعارات التلقائية"))
        except:
            pass
        return

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
