import os
import json
import random
import threading
import time
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# إعداد التوقيت (UTC+3)
TIMEZONE = timezone(timedelta(hours=3))

def get_current_time():
    """الحصول على الوقت الحالي بتوقيت +3"""
    return datetime.now(TIMEZONE)

# تحميل متغيرات البيئة
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("❌ تأكد من وضع مفاتيح LINE في ملف .env")

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ═══════════════════════════════════════════════════════════
# تحميل وحفظ البيانات
# ═══════════════════════════════════════════════════════════

DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"

def load_data():
    """تحميل بيانات المستخدمين والمجموعات"""
    if not os.path.exists(DATA_FILE):
        return {
            "users": [],
            "groups": [],
            "tasbih": {},
            "notifications_off": [],
            "user_cities": {},
            "quran_progress": {},
            "last_morning": {},
            "last_evening": {},
            "last_sleep": {}
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ خطأ في قراءة data.json، سيتم إنشاء ملف جديد")
        return {
            "users": [],
            "groups": [],
            "tasbih": {},
            "notifications_off": [],
            "user_cities": {},
            "quran_progress": {},
            "last_morning": {},
            "last_evening": {},
            "last_sleep": {}
        }

def save_data():
    """حفظ البيانات بشكل آمن"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ خطأ في حفظ البيانات: {e}")

data = load_data()

# ═══════════════════════════════════════════════════════════
# المحتوى الإسلامي
# ═══════════════════════════════════════════════════════════

MORNING_ATHKAR = [
    "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ",
    "اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ النُّشُورُ",
    "أَصْبَحْنَا عَلَى فِطْرَةِ الْإِسْلَامِ، وَعَلَى كَلِمَةِ الْإِخْلَاصِ، وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ",
    "سُبْحَانَ اللهِ وَبِحَمْدِهِ عَدَدَ خَلْقِهِ، وَرِضَا نَفْسِهِ، وَزِنَةَ عَرْشِهِ، وَمِدَادَ كَلِمَاتِهِ",
    "اللَّهُمَّ إِنِّي أَصْبَحْتُ أُشْهِدُكَ أَنَّكَ أَنْتَ اللَّهُ لَا إِلَهَ إِلَّا أَنْتَ"
]

EVENING_ATHKAR = [
    "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ",
    "اللَّهُمَّ بِكَ أَمْسَيْنَا، وَبِكَ أَصْبَحْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ الْمَصِيرُ",
    "أَمْسَيْنَا عَلَى فِطْرَةِ الْإِسْلَامِ، وَعَلَى كَلِمَةِ الْإِخْلَاصِ، وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ",
    "اللَّهُمَّ إِنِّي أَمْسَيْتُ أُشْهِدُكَ أَنَّكَ أَنْتَ اللَّهُ لَا إِلَهَ إِلَّا أَنْتَ"
]

SLEEP_ATHKAR = [
    "بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
    "اللَّهُمَّ إِنَّكَ خَلَقْتَ نَفْسِي وَأَنْتَ تَوَفَّاهَا، لَكَ مَمَاتُهَا وَمَحْيَاهَا",
    "اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ",
    "بِاسْمِكَ رَبِّي وَضَعْتُ جَنْبِي، وَبِكَ أَرْفَعُهُ، فَإِنْ أَمْسَكْتَ نَفْسِي فَارْحَمْهَا"
]

DUAS = [
    "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ",
    "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ",
    "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنْ عَذَابِ جَهَنَّمَ، وَمِنْ عَذَابِ الْقَبْرِ",
    "رَبِّ اغْفِرْ لِي وَلِوَالِدَيَّ وَلِلْمُؤْمِنِينَ يَوْمَ يَقُومُ الْحِسَابُ"
]

HADITHS = [
    "مَنْ قَالَ: سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، فِي يَوْمٍ مِائَةَ مَرَّةٍ، حُطَّتْ خَطَايَاهُ",
    "الْمُؤْمِنُ الْقَوِيُّ خَيْرٌ وَأَحَبُّ إِلَى اللَّهِ مِنَ الْمُؤْمِنِ الضَّعِيفِ",
    "أَحَبُّ الْأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ",
    "الطُّهُورُ شَطْرُ الْإِيمَانِ، وَالْحَمْدُ لِلَّهِ تَمْلَأُ الْمِيزَانَ"
]

QURAN_VERSES = [
    "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
    "فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ",
    "وَمَا خَلَقْتُ الْجِنَّ وَالْإِنسَ إِلَّا لِيَعْبُدُونِ",
    "وَلَا تَيْأَسُوا مِن رَّوْحِ اللَّهِ"
]

# ═══════════════════════════════════════════════════════════
# 🕌 نظام أوقات الصلاة
# ═══════════════════════════════════════════════════════════

def get_prayer_times(city="Riyadh"):
    """الحصول على أوقات الصلاة"""
    try:
        today = get_current_time().strftime("%d-%m-%Y")
        url = f"http://api.aladhan.com/v1/timingsByCity/{today}?city={city}&country=Saudi%20Arabia&method=4"
        response = requests.get(url, timeout=10)
        data_response = response.json()
        if data_response["code"] == 200:
            timings = data_response["data"]["timings"]
            return {
                "الفجر": timings["Fajr"],
                "الظهر": timings["Dhuhr"],
                "العصر": timings["Asr"],
                "المغرب": timings["Maghrib"],
                "العشاء": timings["Isha"]
            }
    except Exception as e:
        print(f"⚠️ خطأ في الحصول على أوقات الصلاة: {e}")
    return None

def check_prayer_times():
    """التحقق من أوقات الصلاة وإرسال التنبيهات"""
    print("🕌 بدأ نظام تنبيهات أوقات الصلاة")
    while True:
        try:
            now = get_current_time()
            current_time = now.strftime("%H:%M")
            
            for user_id, city in list(data["user_cities"].items()):
                if user_id in data["notifications_off"]:
                    continue
                
                prayer_times = get_prayer_times(city)
                if not prayer_times:
                    continue
                
                for prayer, time_str in prayer_times.items():
                    try:
                        prayer_time = datetime.strptime(time_str, "%H:%M")
                        alert_time = (prayer_time - timedelta(minutes=10)).strftime("%H:%M")
                        
                        if current_time == alert_time:
                            message = f"🕌 حان وقت صلاة {prayer}\n⏰ بعد 10 دقائق: {time_str}\n\nاللَّهُمَّ إِنِّي أَسْأَلُكَ الْفِرْدَوْسَ الْأَعْلَى"
                            try:
                                line_bot_api.push_message(user_id, TextSendMessage(text=message))
                            except:
                                pass
                    except:
                        pass
            
            time.sleep(60)
        except Exception as e:
            print(f"⚠️ خطأ في التحقق من أوقات الصلاة: {e}")
            time.sleep(60)

threading.Thread(target=check_prayer_times, daemon=True).start()

# ═══════════════════════════════════════════════════════════
# 📖 نظام قراءة القرآن
# ═══════════════════════════════════════════════════════════

def get_daily_quran_verse():
    """الحصول على آية قرآنية عشوائية"""
    try:
        url = "https://api.alquran.cloud/v1/ayah/random/ar.alafasy"
        response = requests.get(url, timeout=10)
        data_response = response.json()
        if data_response["code"] == 200:
            ayah_data = data_response["data"]
            text = ayah_data["text"]
            surah_name = ayah_data["surah"]["name"]
            number = ayah_data["numberInSurah"]
            return f"📖 {text}\n\n﴿ {surah_name} - آية {number} ﴾"
    except:
        pass
    return f"📖 {random.choice(QURAN_VERSES)}"

def init_quran_progress(user_id):
    """تهيئة تقدم قراءة القرآن"""
    if user_id not in data["quran_progress"]:
        data["quran_progress"][user_id] = {
            "current_juz": 1,
            "completed_juz": [],
            "last_read": None
        }
        save_data()

# ═══════════════════════════════════════════════════════════
# 🌙 التذكير التلقائي
# ═══════════════════════════════════════════════════════════

def send_message(to, text):
    """إرسال رسالة لمستخدم أو مجموعة محددة"""
    try:
        line_bot_api.push_message(to, TextSendMessage(text=text))
        return True
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال إلى {to}: {e}")
        return False

def send_morning_athkar():
    """إرسال أذكار الصباح"""
    print("🌅 إرسال أذكار الصباح")
    today = get_current_time().date().isoformat()
    
    for uid in data["users"]:
        if uid not in data["notifications_off"] and data["last_morning"].get(uid) != today:
            message = f"☀️ صباح الخير\nأذكار الصباح:\n\n{random.choice(MORNING_ATHKAR)}"
            send_message(uid, message)
            data["last_morning"][uid] = today
            time.sleep(0.5)
    
    for gid in data["groups"]:
        if gid not in data["notifications_off"] and data["last_morning"].get(gid) != today:
            message = f"☀️ صباح الخير\nأذكار الصباح:\n\n{random.choice(MORNING_ATHKAR)}"
            send_message(gid, message)
            data["last_morning"][gid] = today
            time.sleep(0.5)
    
    save_data()

def send_evening_athkar():
    """إرسال أذكار المساء"""
    print("🌇 إرسال أذكار المساء")
    today = get_current_time().date().isoformat()
    
    for uid in data["users"]:
        if uid not in data["notifications_off"] and data["last_evening"].get(uid) != today:
            message = f"🌙 مساء الخير\nأذكار المساء:\n\n{random.choice(EVENING_ATHKAR)}"
            send_message(uid, message)
            data["last_evening"][uid] = today
            time.sleep(0.5)
    
    for gid in data["groups"]:
        if gid not in data["notifications_off"] and data["last_evening"].get(gid) != today:
            message = f"🌙 مساء الخير\nأذكار المساء:\n\n{random.choice(EVENING_ATHKAR)}"
            send_message(gid, message)
            data["last_evening"][gid] = today
            time.sleep(0.5)
    
    save_data()

def send_sleep_athkar():
    """إرسال أذكار النوم"""
    print("😴 إرسال أذكار النوم")
    today = get_current_time().date().isoformat()
    
    for uid in data["users"]:
        if uid not in data["notifications_off"] and data["last_sleep"].get(uid) != today:
            message = f"😴 أذكار النوم:\n\n{random.choice(SLEEP_ATHKAR)}"
            send_message(uid, message)
            data["last_sleep"][uid] = today
            time.sleep(0.5)
    
    for gid in data["groups"]:
        if gid not in data["notifications_off"] and data["last_sleep"].get(gid) != today:
            message = f"😴 أذكار النوم:\n\n{random.choice(SLEEP_ATHKAR)}"
            send_message(gid, message)
            data["last_sleep"][gid] = today
            time.sleep(0.5)
    
    save_data()

def send_random_reminder():
    """إرسال تذكير عشوائي"""
    content_type = random.choice(["duas", "hadiths", "quran"])
    
    if content_type == "duas":
        message = f"🤲 {random.choice(DUAS)}"
    elif content_type == "hadiths":
        message = f"📿 {random.choice(HADITHS)}"
    else:
        message = f"📖 {random.choice(QURAN_VERSES)}"
    
    timestamp = get_current_time().strftime("%H:%M")
    full_message = f"{message}\n\n⏰ {timestamp}"
    
    for uid in data["users"]:
        if uid not in data["notifications_off"]:
            send_message(uid, full_message)
            time.sleep(0.5)
    
    for gid in data["groups"]:
        if gid not in data["notifications_off"]:
            send_message(gid, full_message)
            time.sleep(0.5)
    
    print(f"✅ تم إرسال تذكير عشوائي: {content_type}")

def daily_scheduler():
    """جدولة التذكيرات اليومية"""
    print("🕐 بدأ جدول التذكيرات اليومية (UTC+3)")
    last_morning_hour = -1
    last_evening_hour = -1
    last_sleep_hour = -1
    
    while True:
        try:
            now = get_current_time()
            hour = now.hour
            
            # أذكار الصباح (6-10 صباحًا)
            if 6 <= hour < 10 and last_morning_hour != hour:
                send_morning_athkar()
                last_morning_hour = hour
            
            # أذكار المساء (4-7 مساءً)
            elif 16 <= hour < 19 and last_evening_hour != hour:
                send_evening_athkar()
                last_evening_hour = hour
            
            # أذكار النوم (9-12 ليلاً)
            elif 21 <= hour < 24 and last_sleep_hour != hour:
                send_sleep_athkar()
                last_sleep_hour = hour
            
            # إعادة تعيين العدادات في بداية اليوم
            if hour == 0:
                last_morning_hour = -1
                last_evening_hour = -1
                last_sleep_hour = -1
            
            time.sleep(1800)  # فحص كل 30 دقيقة
            
        except Exception as e:
            print(f"⚠️ خطأ في جدول التذكيرات: {e}")
            time.sleep(3600)

def scheduled_random_messages():
    """جدولة التذكيرات العشوائية"""
    print("🔀 بدأ جدول التذكيرات العشوائية")
    while True:
        try:
            sleep_time = random.randint(14400, 21600)  # 4-6 ساعات
            time.sleep(sleep_time)
            send_random_reminder()
        except Exception as e:
            print(f"⚠️ خطأ في التذكيرات العشوائية: {e}")
            time.sleep(3600)

# تشغيل الجداول
threading.Thread(target=daily_scheduler, daemon=True).start()
threading.Thread(target=scheduled_random_messages, daemon=True).start()

# ═══════════════════════════════════════════════════════════
# 📿 نظام التسبيح
# ═══════════════════════════════════════════════════════════

TASBIH_LIMIT = 33
TASBIH_TYPES = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله"]

def ensure_user_counts(uid):
    """التأكد من وجود عداد للمستخدم"""
    if uid not in data["tasbih"]:
        data["tasbih"][uid] = {t: 0 for t in TASBIH_TYPES}

def reset_tasbih(uid):
    """إعادة تعيين عداد التسبيح"""
    data["tasbih"][uid] = {t: 0 for t in TASBIH_TYPES}
    save_data()

def get_tasbih_progress(uid):
    """الحصول على تقدم التسبيح"""
    counts = data["tasbih"][uid]
    lines = []
    for t in TASBIH_TYPES:
        count = counts[t]
        percentage = (count / TASBIH_LIMIT) * 100
        filled = int(percentage / 10)
        bar = "" * filled + "" * (10 - filled)
        lines.append(f"{t}\n{count}/33  {bar}")
    return "\n\n".join(lines)

# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def home():
    return "🕌 بوت ذكرني يعمل بنجاح ✅", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("⚠️ توقيع غير صالح")
        return "Invalid signature", 400
    except Exception as e:
        print(f"⚠️ خطأ في معالجة الطلب: {e}")
        return "Error", 500
    return "OK", 200

# ═══════════════════════════════════════════════════════════
# معالج الرسائل
# ═══════════════════════════════════════════════════════════

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        group_id = getattr(event.source, "group_id", None)
        target_id = user_id or group_id
        
        # ════════════════════════════════════════════════
        # تسجيل المستخدمين والمجموعات تلقائياً
        # ════════════════════════════════════════════════
        is_new = False
        
        if user_id and user_id not in data["users"]:
            data["users"].append(user_id)
            is_new = True
            save_data()
            print(f"✅ مستخدم جديد: {user_id}")
        
        if group_id and group_id not in data["groups"]:
            data["groups"].append(group_id)
            is_new = True
            save_data()
            print(f"✅ مجموعة جديدة: {group_id}")
        
        ensure_user_counts(target_id)
        init_quran_progress(target_id)
        
        # ════════════════════════════════════════════════
        # أمر: مساعدة
        # ════════════════════════════════════════════════
        if user_text.lower() in ["مساعدة", "help"]:
            help_text = """🌙 أوامر البوت الإسلامي

📿 التسبيح:
• سبحان الله / الحمد لله / الله أكبر / استغفر الله
• تسبيح - عرض التقدم
• إعادة - إعادة العداد

🕌 أوقات الصلاة:
• مدينتي [اسم المدينة]
• أوقات الصلاة

📖 القرآن:
• آية - آية قرآنية
• ختمتي - تقدم القراءة
• قرأت جزء [رقم]

🌙 الأذكار:
• أذكار الصباح
• أذكار المساء
• أذكار النوم

📨 التذكير:
• ذكرني - ذكر فوري
• دعاء - دعاء عشوائي
• حديث - حديث شريف
• إيقاف - إيقاف التذكير
• تشغيل - تشغيل التذكير

━━━━━━━━━━━━━━━━━
جزاك الله خيراً 🖤"""
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
            return
        
        # ════════════════════════════════════════════════
        # تسجيل المدينة
        # ════════════════════════════════════════════════
        if user_text.lower().startswith("مدينتي"):
            city = user_text.replace("مدينتي", "").strip()
            if city:
                data["user_cities"][user_id] = city
                save_data()
                line_bot_api.reply_message(event.reply_token, 
                    TextSendMessage(text=f"✅ تم تسجيل مدينتك: {city}\nستصلك تنبيهات الصلاة قبل 10 دقائق"))
            return
        
        # ════════════════════════════════════════════════
        # أوقات الصلاة
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أوقات الصلاة", "الصلاة", "مواقيت"]:
            city = data["user_cities"].get(user_id, "Riyadh")
            prayer_times = get_prayer_times(city)
            if prayer_times:
                msg = f"🕌 أوقات الصلاة في {city}\n\n"
                for prayer, time in prayer_times.items():
                    msg += f"{prayer}: {time}\n"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            else:
                line_bot_api.reply_message(event.reply_token, 
                    TextSendMessage(text="⚠️ عذراً، لم نستطع الحصول على أوقات الصلاة"))
            return
        
        # ════════════════════════════════════════════════
        # آية قرآنية
        # ════════════════════════════════════════════════
        if user_text.lower() in ["آية", "قرآن", "اية"]:
            verse = get_daily_quran_verse()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=verse))
            return
        
        # ════════════════════════════════════════════════
        # تقدم القراءة
        # ════════════════════════════════════════════════
        if user_text.lower() in ["ختمتي", "القراءة", "تقدمي"]:
            progress = data["quran_progress"][target_id]
            completed = len(progress["completed_juz"])
            msg = f"📖 تقدم قراءة القرآن\n\nالجزء الحالي: {progress['current_juz']}\nالأجزاء المكتملة: {completed}/30"
            if completed == 30:
                msg += "\n\n🎉 ماشاء الله! أتممت ختمة كاملة!\nبارك الله فيك 💚"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        # ════════════════════════════════════════════════
        # تسجيل قراءة جزء
        # ════════════════════════════════════════════════
        if user_text.lower().startswith("قرأت جزء"):
            try:
                juz_num = int(user_text.split()[-1])
                if 1 <= juz_num <= 30:
                    if juz_num not in data["quran_progress"][target_id]["completed_juz"]:
                        data["quran_progress"][target_id]["completed_juz"].append(juz_num)
                        data["quran_progress"][target_id]["current_juz"] = min(juz_num + 1, 30)
                        save_data()
                        line_bot_api.reply_message(event.reply_token, 
                            TextSendMessage(text=f"✨ ماشاء الله!\nتم تسجيل الجزء {juz_num}\nبارك الله فيك 💚"))
                    else:
                        line_bot_api.reply_message(event.reply_token, 
                            TextSendMessage(text=f"✅ الجزء {juz_num} مسجل مسبقاً"))
            except:
                pass
            return
        
        # ════════════════════════════════════════════════
        # أذكار الصباح
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أذكار الصباح", "اذكار الصباح", "الصباح"]:
            msg = "☀️ أذكار الصباح\n\n" + "\n\n━━━━━━━━━━━\n\n".join(MORNING_ATHKAR[:3])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        # ════════════════════════════════════════════════
        # أذكار المساء
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أذكار المساء", "اذكار المساء", "المساء"]:
            msg = "🌙 أذكار المساء\n\n" + "\n\n━━━━━━━━━━━\n\n".join(EVENING_ATHKAR[:3])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        # ════════════════════════════════════════════════
        # أذكار النوم
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أذكار النوم", "اذكار النوم", "النوم"]:
            msg = "😴 أذكار النوم\n\n" + "\n\n━━━━━━━━━━━\n\n".join(SLEEP_ATHKAR[:3])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        # ════════════════════════════════════════════════
        # دعاء
        # ════════════════════════════════════════════════
        if user_text.lower() in ["دعاء", "ادعية"]:
            msg = f"🤲 {random.choice(DUAS)}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        # ════════════════════════════════════════════════
        # حديث
        # ════════════════════════════════════════════════
        if user_text.lower() in ["حديث", "احاديث"]:
            msg = f"📿 {random.choice(HADITHS)}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        # ════════════════════════════════════════════════
        # عرض التسبيح
        # ════════════════════════════════════════════════
        if user_text.lower() in ["تسبيح", "عداد"]:
            progress_text = get_tasbih_progress(target_id)
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text=f"📿 تقدم التسبيح\n\n{progress_text}"))
            return
        
        # ════════════════════════════════════════════════
        # إعادة التسبيح
        # ════════════════════════════════════════════════
        if user_text.lower() in ["إعادة", "reset", "اعادة"]:
            reset_tasbih(target_id)
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text="✅ تم إعادة تعيين عداد التسبيح"))
            return
        
        # ════════════════════════════════════════════════
        # التسبيح
        # ════════════════════════════════════════════════
        clean_text = user_text.replace(" ", "")
        key_map = {
            "سبحانالله": "سبحان الله",
            "الحمدلله": "الحمد لله",
            "اللهأكبر": "الله أكبر",
            "استغفرالله": "استغفر الله"
        }
        
        key = key_map.get(clean_text)
        if key:
            if data["tasbih"][target_id][key] < TASBIH_LIMIT:
                data["tasbih"][target_id][key] += 1
                save_data()
            
            if data["tasbih"][target_id][key] == TASBIH_LIMIT:
                line_bot_api.push_message(target_id, 
                    TextSendMessage(text=f"✨ ماشاء الله!\nاكتملت {key} 33 مرة! "))
            
            progress_text = get_tasbih_progress(target_id)
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text=f"📿 {progress_text}"))
            
            counts = data["tasbih"][target_id]
            if all(counts[k] >= TASBIH_LIMIT for k in TASBIH_TYPES):
                line_bot_api.push_message(target_id, 
                    TextSendMessage(text="🎉 مبروك! اكتملت كل الأذكار!\n\nجزاك الله خيراً\nوجعل الله لك ولوالديك الجنة 💚"))
            return
        
        # ════════════════════════════════════════════════
        # ذكرني - إرسال لجميع المستخدمين
        # ════════════════════════════════════════════════
        if user_text.lower() in ["ذكرني", "تذكير", "ذكر"]:
            content_type = random.choice(["duas", "hadiths", "quran"])
            if content_type == "duas":
                message = f"🤲 {random.choice(DUAS)}"
            elif content_type == "hadiths":
                message = f"📿 {random.choice(HADITHS)}"
            else:
                message = f"📖 {random.choice(QURAN_VERSES)}"
            
            timestamp = get_current_time().strftime("%H:%M")
            full_message = f"{message}\n\n⏰ {timestamp}"
            
            # إرسال للجميع
            success_count = 0
            for uid in data["users"]:
                if uid not in data["notifications_off"]:
                    if send_message(uid, full_message):
                        success_count += 1
                    time.sleep(0.5)
            
            for gid in data["groups"]:
                if gid not in data["notifications_off"]:
                    if send_message(gid, full_message):
                        success_count += 1
                    time.sleep(0.5)
            
            # تأكيد للمرسل
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text=f"📣 تم إرسال التذكير\n\n{message}\n\n✅ وصل إلى {success_count} متلقي"))
            return
        
        # ════════════════════════════════════════════════
        # إيقاف
        # ════════════════════════════════════════════════
        if user_text.lower() in ["إيقاف", "stop", "ايقاف"]:
            if target_id not in data["notifications_off"]:
                data["notifications_off"].append(target_id)
                save_data()
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text="⏸️ تم إيقاف التذكير التلقائي\n\nلتشغيله اكتب: تشغيل"))
            return
        
        # ════════════════════════════════════════════════
        # تشغيل
        # ════════════════════════════════════════════════
        if user_text.lower() in ["تشغيل", "start", "بدء"]:
            if target_id in data["notifications_off"]:
                data["notifications_off"].remove(target_id)
                save_data()
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text="✅ تم تشغيل التذكير التلقائي 🌙"))
            return
        
        # ════════════════════════════════════════════════
        # رد افتراضي للمستخدمين الجدد
        # ════════════════════════════════════════════════
        if is_new:
            welcome_text = """🌙 السلام عليكم ورحمة الله وبركاته

✨ مرحبًا بك في بوت *ذكّرني*

📿 سيساعدك هذا البوت على:
• تذكّر أذكار الصباح والمساء والنوم
• متابعة التسبيح اليومي
• الحصول على أدعية وآيات قرآنية
• تنبيهات أوقات الصلاة
• متابعة قراءة القرآن

🔹 اكتب *مساعدة* لعرض قائمة الأوامر

🤲 جزاك الله خيرًا"""
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_text))
    
    except Exception as e:
        print(f"⚠️ خطأ في معالجة الرسالة: {e}")

# ═══════════════════════════════════════════════════════════
# تشغيل التطبيق
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔═══════════════════════════════╗")
    print("║   🕌 بوت ذكرني الإسلامي   ║")
    print("╚═══════════════════════════════╝")
    print(f"🚀 المنفذ: {PORT}")
    print(f"🕐 التوقيت: UTC+3 (السعودية)")
    print(f"⏰ الوقت الحالي: {get_current_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"👥 المستخدمين: {len(data['users'])}")
    print(f"👥 المجموعات: {len(data['groups'])}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ البوت يعمل الآن...")
    print("📝 ملاحظة: يتم تسجيل المستخدمين تلقائياً بعد أول رسالة")
    app.run(host="0.0.0.0", port=PORT, debug=False)
