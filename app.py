from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time
from datetime import datetime, timedelta
import pytz
from praytimes import PrayTimes  # pip install praytimes
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
            json.dump({"users": [], "groups": [], "tasbih": {}}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("users", [])), set(data.get("groups", [])), data.get("tasbih", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": list(target_users),
            "groups": list(target_groups),
            "tasbih": tasbih_counts
        }, f, ensure_ascii=False, indent=2)

target_users, target_groups, tasbih_counts = load_data()

# ---------------- تحميل المحتوى ---------------- #
content = {}
if os.path.exists(CONTENT_FILE):
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)

# ---------------- أذكار الصباح والمساء والنوم ---------------- #
morning_adhkar = [
    "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت",
    "أصبحنا على فطرة الإسلام وعلى كلمة الإخلاص وعلى دين نبينا محمد"
]

evening_adhkar = [
    "أمسينا على فطرة الإسلام وعلى كلمة الإخلاص وعلى دين نبينا محمد",
    "اللهم ما أمسينا فيه من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك"
]

sleep_adhkar = [
    "باسمك ربي وضعت جنبي وبك أرفعه",
    "اللهم قني عذابك يوم تبعث عبادك"
]

def send_adhkar_list_to_all(adhkar_list):
    for message in adhkar_list:
        for uid in target_users:
            try:
                line_bot_api.push_message(uid, TextSendMessage(text=message))
            except:
                pass
        for gid in target_groups:
            try:
                line_bot_api.push_message(gid, TextSendMessage(text=message))
            except:
                pass

# ---------------- التذكير حسب أوقات الصلاة + الأذكار ---------------- #
def schedule_prayer_adhkar():
    tz = pytz.timezone('Asia/Riyadh')
    pt = PrayTimes('ISNA')
    latitude, longitude = 24.7136, 46.6753  # موقع الرياض

    while True:
        now = datetime.now(tz)
        times = pt.getTimes(now, (latitude, longitude), +3)
        prayer_times = {prayer: datetime.strptime(times[prayer], '%H:%M').replace(
            year=now.year, month=now.month, day=now.day, tzinfo=tz) for prayer in ['Fajr','Dhuhr','Asr','Maghrib','Isha']}

        # قبل كل صلاة بـ 10 دقائق
        for prayer, p_time in prayer_times.items():
            notify_time = p_time - timedelta(minutes=10)
            wait_seconds = (notify_time - datetime.now(tz)).total_seconds()
            if wait_seconds > 0:
                time.sleep(wait_seconds)
                # إرسال الأذكار حسب الصلاة
                if prayer == 'Fajr':
                    send_adhkar_list_to_all(morning_adhkar)
                elif prayer == 'Maghrib':
                    send_adhkar_list_to_all(evening_adhkar)
                elif prayer == 'Isha':
                    send_adhkar_list_to_all(sleep_adhkar)

        # الانتظار لبداية اليوم التالي
        tomorrow = now + timedelta(days=1)
        next_day = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, tzinfo=tz)
        time.sleep((next_day - datetime.now(tz)).total_seconds())

threading.Thread(target=schedule_prayer_adhkar, daemon=True).start()

# ---------------- إرسال ذكر/دعاء/حديث عشوائي ---------------- #
def send_random_message_to_all():
    category = random.choice(["duas", "adhkar", "hadiths"])
    message = "لا يوجد محتوى"
    if category in content and content[category]:
        message = random.choice(content[category])
    for uid in target_users:
        try:
            line_bot_api.push_message(uid, TextSendMessage(text=message))
        except:
            pass
    for gid in target_groups:
        try:
            line_bot_api.push_message(gid, TextSendMessage(text=message))
        except:
            pass

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
    try:
        text = event.message.text.strip()
        if "http://" in text or "https://" in text or "www." in text:
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] >= 2:
                try:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
                except:
                    pass
            return True
    except:
        pass
    return False

# ---------------- تسبيح ---------------- #
tasbih_limits = 33
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0, "استغفر الله":0}

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id

        # تسجيل المستخدمين والقروبات تلقائي
        first_time = False
        if user_id not in target_users:
            target_users.add(user_id)
            first_time = True
        gid = getattr(event.source, 'group_id', None)
        if gid and gid not in target_groups:
            target_groups.add(gid)
            first_time = True
        save_data()
        ensure_user_counts(user_id)

        # إرسال ذكر/دعاء/حديث عند التسجيل لأول مرة
        if first_time:
            try:
                category = random.choice(["duas", "adhkar", "hadiths"])
                if category in content and content[category]:
                    message = random.choice(content[category])
                    line_bot_api.push_message(user_id, TextSendMessage(text=message))
            except:
                pass
            return

        # حماية الروابط
        if handle_links(event, user_id):
            return

        # أوامر المساعدة
        if user_text.lower() == "مساعدة":
            try:
                with open("help.txt", "r", encoding="utf-8") as f:
                    help_text = f.read()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
            except:
                pass
            return

        # عرض التسبيح
        if user_text.lower() == "تسبيح":
            counts = tasbih_counts[user_id]
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33\nاستغفر الله: {counts['استغفر الله']}/33"
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
            except:
                pass
            return

        # التسبيح (زيادة العد)
        if user_text in ("سبحان الله","الحمد لله","الله أكبر","استغفر الله","استغفرالله"):
            key = "استغفر الله" if "استغفر" in user_text else user_text
            tasbih_counts[user_id][key] += 1
            save_data()
            counts = tasbih_counts[user_id]
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33\nاستغفر الله: {counts['استغفر الله']}/33"
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
            except:
                pass
            return

        # أمر ذكرني يدوي
        if user_text.lower() == "ذكرني":
            send_random_message_to_all()
            return

    except:
        pass

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
