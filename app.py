import os
import json
import random
import time
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# ───────────── إعداد التوقيت ─────────────
TIMEZONE = timezone(timedelta(hours=3))

def get_current_time():
    return datetime.now(TIMEZONE)

# ───────────── تحميل متغيرات البيئة ─────────────
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("❌ تأكد من وضع مفاتيح LINE في ملف .env")

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

DATA_FILE = "data.json"
HELP_FILE = "help.txt"

# ───────────── إدارة البيانات ─────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": [],
            "groups": [],
            "notifications_off": [],
            "tasbeeh_count": {}
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {
            "users": [],
            "groups": [],
            "notifications_off": [],
            "tasbeeh_count": {}
        }

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ خطأ في حفظ البيانات: {e}")

data = load_data()

# ───────────── المحتوى الإسلامي ─────────────
MORNING_ATHKAR = [
    "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ",
    "اللَّهُمَّ بِكَ أَصْبَحْنَا وَبِكَ أَمْسَيْنَا وَبِكَ نَحْيَا وَبِكَ نَمُوتُ وَإِلَيْكَ النُّشُور",
    "أَصْبَحْنَا عَلَى فِطْرَةِ الْإِسْلَامِ وَعَلَى كَلِمَةِ الْإِخْلَاص وَعَلَى دِينِ نَبِيِّنَا مُحَمَّد ﷺ"
]

EVENING_ATHKAR = [
    "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ وَالْحَمْدُ لِلَّهِ",
    "اللَّهُمَّ بِكَ أَمْسَيْنَا وَبِكَ أَصْبَحْنَا وَبِكَ نَحْيَا وَبِكَ نَمُوتُ وَإِلَيْكَ الْمَصِير",
    "أَمْسَيْنَا عَلَى فِطْرَةِ الْإِسْلَامِ وَعَلَى كَلِمَةِ الْإِخْلَاص وَعَلَى دِينِ نَبِيِّنَا مُحَمَّد ﷺ"
]

SLEEP_ATHKAR = [
    "بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
    "اللَّهُمَّ إِنَّكَ خَلَقْتَ نَفْسِي وَأَنْتَ تَوَفَّاهَا، لَكَ مَمَاتُهَا وَمَحْيَاهَا",
    "اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ"
]

DUAS = [
    "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ",
    "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ"
]

HADITHS = [
    "مَنْ قَالَ: سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، فِي يَوْمٍ مِائَةَ مَرَّةٍ، حُطَّتْ خَطَايَاهُ",
    "الْمُؤْمِنُ الْقَوِيُّ خَيْرٌ وَأَحَبُّ إِلَى اللَّهِ مِنَ الْمُؤْمِنِ الضَّعِيفِ"
]

QURAN_VERSES = [
    "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
    "فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ"
]

# ───────────── إرسال الرسائل ─────────────
def send_message(to, text):
    try:
        line_bot_api.push_message(to, TextSendMessage(text=text))
        return True
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال إلى {to}: {e}")
        return False

# ───────────── وظيفة الأذكار الذكية ─────────────
def auto_athkar():
    while True:
        now = get_current_time()
        hour = now.hour
        minute = now.minute

        # الصباح 5:00 - 9:00
        if 5 <= hour < 9 and minute == 0:
            message = f"☀️ أذكار الصباح:\n{random.choice(MORNING_ATHKAR)}"
            for uid in data["users"]:
                if uid not in data["notifications_off"]:
                    send_message(uid, message)
            for gid in data["groups"]:
                if gid not in data["notifications_off"]:
                    send_message(gid, message)

        # المساء 18:00 - 22:00
        if 18 <= hour < 22 and minute == 0:
            message = f"🌙 أذكار المساء:\n{random.choice(EVENING_ATHKAR)}"
            for uid in data["users"]:
                if uid not in data["notifications_off"]:
                    send_message(uid, message)
            for gid in data["groups"]:
                if gid not in data["notifications_off"]:
                    send_message(gid, message)

        # أذكار النوم 23:00
        if hour == 23 and minute == 0:
            message = f"💤 أذكار النوم:\n{random.choice(SLEEP_ATHKAR)}"
            for uid in data["users"]:
                if uid not in data["notifications_off"]:
                    send_message(uid, message)
            for gid in data["groups"]:
                if gid not in data["notifications_off"]:
                    send_message(gid, message)

        time.sleep(60)  # تحقق كل دقيقة

# ───────────── Routes ─────────────
@app.route("/", methods=["GET"])
def home():
    return "🕌 بوت ذكرني الإسلامي الذكي يعمل بنجاح ✅", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    except Exception as e:
        print(f"⚠️ خطأ في معالجة الطلب: {e}")
        return "Error", 500
    return "OK", 200

# ───────────── معالج الرسائل ─────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        group_id = getattr(event.source, "group_id", None)
        target_id = user_id or group_id

        # تسجيل المستخدمين والمجموعات
        if user_id and user_id not in data["users"]:
            data["users"].append(user_id)
            save_data()
        if group_id and group_id not in data["groups"]:
            data["groups"].append(group_id)
            save_data()

        # ───── أمر المساعدة ─────
        if user_text.lower() in ["مساعدة", "help"]:
            try:
                with open(HELP_FILE, "r", encoding="utf-8") as f:
                    help_text = f.read()
            except:
                help_text = "⚠️ لا يوجد محتوى المساعدة"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
            return

        # ───── أمر ذكرني ─────
        if user_text.lower() in ["ذكرني", "تذكير", "ذكر"]:
            content_type = random.choice(["duas", "hadiths", "quran"])
            if content_type == "duas":
                message = f"🤲 {random.choice(DUAS)}"
            elif content_type == "hadiths":
                message = f"📿 {random.choice(HADITHS)}"
            else:
                message = f"📖 {random.choice(QURAN_VERSES)}"

            # زيادة عداد التسبيح
            if user_id:
                data["tasbeeh_count"][user_id] = data["tasbeeh_count"].get(user_id, 0) + 1
                save_data()

            # إرسال لجميع المستخدمين والمجموعات
            for uid in data["users"]:
                if uid not in data["notifications_off"]:
                    send_message(uid, message)
                    time.sleep(0.5)
            for gid in data["groups"]:
                if gid not in data["notifications_off"]:
                    send_message(gid, message)
                    time.sleep(0.5)

            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text="✨ تم إرسال الذكر لجميع المستخدمين والمجموعات"))
            return

        # ───── أمر عرض عدد التسبيح ─────
        if user_text.lower() in ["عدد التسبيح", "عدد"]:
            count = data["tasbeeh_count"].get(user_id, 0)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"🕋 عدد مرات استخدامك لأمر الذكر اليوم: {count}"))
            return

    except Exception as e:
        print(f"⚠️ خطأ في معالجة الرسالة: {e}")

# ───────────── تشغيل التطبيق ─────────────
if __name__ == "__main__":
    # تشغيل الثريد الخاص بالأذكار الذكية
    threading.Thread(target=auto_athkar, daemon=True).start()

    print("╔════════════════════════════════╗")
    print("║   🕌 بوت ذكرني الإسلامي الذكي   ║")
    print("╚════════════════════════════════╝")
    print(f"🚀 المنفذ: {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
