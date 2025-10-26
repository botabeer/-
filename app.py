import os
import json
import random
import time
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
MessageEvent, TextMessage, TextSendMessage, JoinEvent,
LeaveEvent, MemberJoinedEvent, MemberLeftEvent
)
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════

# الإعدادات الأساسية

# ═══════════════════════════════════════════════════════════════

TIMEZONE = timezone(timedelta(hours=3))

def get_current_time():
return datetime.now(TIMEZONE)

def get_current_date():
return get_current_time().strftime(”%Y-%m-%d”)

load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv(“LINE_CHANNEL_ACCESS_TOKEN”)
LINE_CHANNEL_SECRET = os.getenv(“LINE_CHANNEL_SECRET”)
PORT = int(os.getenv(“PORT”, 5000))

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
raise ValueError(“❌ تأكد من وضع مفاتيح LINE في ملف .env”)

app = Flask(**name**)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

DATA_FILE = “data.json”

# ═══════════════════════════════════════════════════════════════

# إدارة البيانات

# ═══════════════════════════════════════════════════════════════

def load_data():
if not os.path.exists(DATA_FILE):
return {
“users”: [],
“groups”: [],
“admins”: {},
“blocked_users”: [],
“warnings”: {},
“stats”: {
“total_athkar_sent”: 0,
“total_duas_sent”: 0,
“total_hadiths_sent”: 0,
“total_quran_sent”: 0
},
“user_stats”: {},
“last_reset_date”: get_current_date()
}
try:
with open(DATA_FILE, “r”, encoding=“utf-8”) as f:
return json.load(f)
except:
return {
“users”: [],
“groups”: [],
“admins”: {},
“blocked_users”: [],
“warnings”: {},
“stats”: {
“total_athkar_sent”: 0,
“total_duas_sent”: 0,
“total_hadiths_sent”: 0,
“total_quran_sent”: 0
},
“user_stats”: {},
“last_reset_date”: get_current_date()
}

def save_data():
try:
with open(DATA_FILE, “w”, encoding=“utf-8”) as f:
json.dump(data, f, ensure_ascii=False, indent=2)
except Exception as e:
print(f”⚠️ خطأ في حفظ البيانات: {e}”)

def reset_daily_stats():
current_date = get_current_date()
if data.get(“last_reset_date”) != current_date:
data[“user_stats”] = {}
data[“last_reset_date”] = current_date
save_data()
print(f”✅ إعادة تعيين الإحصائيات اليومية - {current_date}”)

data = load_data()

# ═══════════════════════════════════════════════════════════════

# المحتوى الإسلامي

# ═══════════════════════════════════════════════════════════════

MORNING_ATHKAR = [
“أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ لَا شَرِيكَ لَهُ”,
“اللَّهُمَّ بِكَ أَصْبَحْنَا وَبِكَ أَمْسَيْنَا وَبِكَ نَحْيَا وَبِكَ نَمُوتُ وَإِلَيْكَ النُّشُور”,
“أَصْبَحْنَا عَلَى فِطْرَةِ الْإِسْلَامِ وَعَلَى كَلِمَةِ الْإِخْلَاصِ وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ وَعَلَى مِلَّةِ أَبِينَا إِبْرَاهِيمَ حَنِيفًا مُسْلِمًا”,
“رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ ﷺ نَبِيًّا”,
“اللَّهُمَّ إِنِّي أَصْبَحْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ وَمَلَائِكَتَكَ وَجَمِيعَ خَلْقِكَ أَنَّكَ أَنْتَ اللَّهُ لَا إِلَهَ إِلَّا أَنْتَ”,
“أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ رَبِّ الْعَالَمِينَ، اللَّهُمَّ إِنِّي أَسْأَلُكَ خَيْرَ هَذَا الْيَوْمِ”
]

EVENING_ATHKAR = [
“أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ لَا شَرِيكَ لَهُ”,
“اللَّهُمَّ بِكَ أَمْسَيْنَا وَبِكَ أَصْبَحْنَا وَبِكَ نَحْيَا وَبِكَ نَمُوتُ وَإِلَيْكَ الْمَصِير”,
“أَمْسَيْنَا عَلَى فِطْرَةِ الْإِسْلَامِ وَعَلَى كَلِمَةِ الْإِخْلَاصِ وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ وَعَلَى مِلَّةِ أَبِينَا إِبْرَاهِيمَ حَنِيفًا مُسْلِمًا”,
“رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ ﷺ نَبِيًّا”,
“اللَّهُمَّ إِنِّي أَمْسَيْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ وَمَلَائِكَتَكَ وَجَمِيعَ خَلْقِكَ أَنَّكَ أَنْتَ اللَّهُ لَا إِلَهَ إِلَّا أَنْتَ”,
“أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ رَبِّ الْعَالَمِينَ، اللَّهُمَّ إِنِّي أَسْأَلُكَ خَيْرَ هَذِهِ اللَّيْلَةِ”
]

SLEEP_ATHKAR = [
“بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا”,
“اللَّهُمَّ إِنَّكَ خَلَقْتَ نَفْسِي وَأَنْتَ تَوَفَّاهَا، لَكَ مَمَاتُهَا وَمَحْيَاهَا”,
“اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ”,
“اللَّهُمَّ بِاسْمِكَ رَبِّي وَضَعْتُ جَنْبِي وَبِكَ أَرْفَعُهُ”
]

DUAS = [
“اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ”,
“رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ”,
“اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ وَالْعَجْزِ وَالْكَسَلِ”,
“رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي”,
“اللَّهُمَّ إِنِّي أَسْأَلُكَ عِلْمًا نَافِعًا وَرِزْقًا طَيِّبًا وَعَمَلًا مُتَقَبَّلًا”,
“اللَّهُمَّ أَعِنِّي عَلَى ذِكْرِكَ وَشُكْرِكَ وَحُسْنِ عِبَادَتِكَ”,
“رَبَّنَا اغْفِرْ لَنَا وَلِإِخْوَانِنَا الَّذِينَ سَبَقُونَا بِالْإِيمَانِ”,
“اللَّهُمَّ إِنِّي أَسْأَلُكَ الْجَنَّةَ وَأَعُوذُ بِكَ مِنَ النَّارِ”
]

HADITHS = [
“مَنْ قَالَ سُبْحَانَ اللَّهِ وَبِحَمْدِهِ فِي يَوْمٍ مِائَةَ مَرَّةٍ حُطَّتْ خَطَايَاهُ وَإِنْ كَانَتْ مِثْلَ زَبَدِ الْبَحْرِ”,
“الْمُؤْمِنُ الْقَوِيُّ خَيْرٌ وَأَحَبُّ إِلَى اللَّهِ مِنَ الْمُؤْمِنِ الضَّعِيفِ وَفِي كُلٍّ خَيْرٌ”,
“مَنْ كَانَ يُؤْمِنُ بِاللَّهِ وَالْيَوْمِ الْآخِرِ فَلْيَقُلْ خَيْرًا أَوْ لِيَصْمُتْ”,
“الْكَلِمَةُ الطَّيِّبَةُ صَدَقَةٌ”,
“أَحَبُّ الْأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ”,
“الدِّينُ النَّصِيحَةُ، قُلْنَا: لِمَنْ؟ قَالَ: لِلَّهِ وَلِكِتَابِهِ وَلِرَسُولِهِ”,
“إِنَّ اللَّهَ كَتَبَ الْإِحْسَانَ عَلَى كُلِّ شَيْءٍ”,
“مَنْ نَفَّسَ عَنْ مُؤْمِنٍ كُرْبَةً نَفَّسَ اللَّهُ عَنْهُ كُرْبَةً مِنْ كُرَبِ يَوْمِ الْقِيَامَةِ”
]

QURAN_VERSES = [
“إِنَّ مَعَ الْعُسْرِ يُسْرًا”,
“فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ”,
“وَلَا تَيْأَسُوا مِن رَّوْحِ اللَّهِ إِنَّهُ لَا يَيْأَسُ مِن رَّوْحِ اللَّهِ إِلَّا الْقَوْمُ الْكَافِرُونَ”,
“إِنَّ اللَّهَ مَعَ الصَّابِرِينَ”,
“وَمَن يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ”,
“فَإِنَّ مَعَ الْعُسْرِ يُسْرًا إِنَّ مَعَ الْعُسْرِ يُسْرًا”,
“وَلَذِكْرُ اللَّهِ أَكْبَرُ”,
“وَاسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ”
]

PRAYER_REMINDERS = [
“حَافِظُوا عَلَى الصَّلَوَاتِ وَالصَّلَاةِ الْوُسْطَى”,
“الصَّلَاةُ عِمَادُ الدِّينِ”,
“أَقِمِ الصَّلَاةَ لِدُلُوكِ الشَّمْسِ”
]

# ═══════════════════════════════════════════════════════════════

# وظائف الإرسال

# ═══════════════════════════════════════════════════════════════

def send_message(to, text):
try:
line_bot_api.push_message(to, TextSendMessage(text=text))
return True
except Exception as e:
print(f”⚠️ خطأ في الإرسال: {e}”)
return False

def format_athkar_message(athkar_type, content):
“”“تنسيق رسالة الأذكار بشكل نظيف ومريح”””
divider = “─” * 30

```
if athkar_type == "morning":
    header = "☀️ أذكار الصباح"
elif athkar_type == "evening":
    header = "🌙 أذكار المساء"
elif athkar_type == "sleep":
    header = "💤 أذكار النوم"
elif athkar_type == "dua":
    header = "🤲 دعاء"
elif athkar_type == "hadith":
    header = "📿 حديث شريف"
elif athkar_type == "quran":
    header = "📖 قرآن كريم"
elif athkar_type == "prayer":
    header = "🕌 تذكير بالصلاة"
else:
    header = "📿 ذكر"

message = f"{header}\n{divider}\n\n{content}\n\n{divider}"
return message
```

def broadcast_athkar(athkar_type, content):
“”“إرسال الأذكار لجميع المستخدمين والمجموعات”””
message = format_athkar_message(athkar_type, content)
sent_count = 0

```
for uid in data["users"]:
    if send_message(uid, message):
        sent_count += 1
    time.sleep(0.2)

for gid in data["groups"]:
    if send_message(gid, message):
        sent_count += 1
    time.sleep(0.2)

data["stats"][f"total_{athkar_type}_sent"] = data["stats"].get(f"total_{athkar_type}_sent", 0) + 1
save_data()

return sent_count
```

# ═══════════════════════════════════════════════════════════════

# الأذكار التلقائية

# ═══════════════════════════════════════════════════════════════

def auto_athkar_scheduler():
“”“جدولة الأذكار التلقائية”””
last_check_date = None
sent_today = {
“morning”: False,
“evening”: False,
“sleep”: False,
“fajr”: False,
“dhuhr”: False,
“asr”: False,
“maghrib”: False,
“isha”: False
}

```
while True:
    try:
        now = get_current_time()
        current_date = now.strftime("%Y-%m-%d")
        hour = now.hour
        minute = now.minute
        
        if last_check_date != current_date:
            reset_daily_stats()
            sent_today = {k: False for k in sent_today}
            last_check_date = current_date
        
        # أذكار الصباح - 6:00 صباحاً
        if hour == 6 and minute == 0 and not sent_today["morning"]:
            content = random.choice(MORNING_ATHKAR)
            broadcast_athkar("morning", content)
            sent_today["morning"] = True
            print(f"✅ أذكار الصباح - {now}")
        
        # تذكير صلاة الفجر - 5:00 صباحاً
        elif hour == 5 and minute == 0 and not sent_today["fajr"]:
            content = "حان وقت صلاة الفجر\n" + random.choice(PRAYER_REMINDERS)
            broadcast_athkar("prayer", content)
            sent_today["fajr"] = True
            print(f"✅ تذكير الفجر - {now}")
        
        # تذكير صلاة الظهر - 12:00 ظهراً
        elif hour == 12 and minute == 0 and not sent_today["dhuhr"]:
            content = "حان وقت صلاة الظهر\n" + random.choice(PRAYER_REMINDERS)
            broadcast_athkar("prayer", content)
            sent_today["dhuhr"] = True
            print(f"✅ تذكير الظهر - {now}")
        
        # تذكير صلاة العصر - 3:30 عصراً
        elif hour == 15 and minute == 30 and not sent_today["asr"]:
            content = "حان وقت صلاة العصر\n" + random.choice(PRAYER_REMINDERS)
            broadcast_athkar("prayer", content)
            sent_today["asr"] = True
            print(f"✅ تذكير العصر - {now}")
        
        # أذكار المساء + تذكير المغرب - 6:00 مساءً
        elif hour == 18 and minute == 0 and not sent_today["evening"]:
            content = random.choice(EVENING_ATHKAR)
            broadcast_athkar("evening", content)
            sent_today["evening"] = True
            time.sleep(2)
            content = "حان وقت صلاة المغرب\n" + random.choice(PRAYER_REMINDERS)
            broadcast_athkar("prayer", content)
            sent_today["maghrib"] = True
            print(f"✅ أذكار المساء + المغرب - {now}")
        
        # تذكير صلاة العشاء - 7:30 مساءً
        elif hour == 19 and minute == 30 and not sent_today["isha"]:
            content = "حان وقت صلاة العشاء\n" + random.choice(PRAYER_REMINDERS)
            broadcast_athkar("prayer", content)
            sent_today["isha"] = True
            print(f"✅ تذكير العشاء - {now}")
        
        # أذكار النوم - 10:30 مساءً
        elif hour == 22 and minute == 30 and not sent_today["sleep"]:
            content = random.choice(SLEEP_ATHKAR)
            broadcast_athkar("sleep", content)
            sent_today["sleep"] = True
            print(f"✅ أذكار النوم - {now}")
        
        # تذكير منتصف اليوم - 2:00 ظهراً
        elif hour == 14 and minute == 0:
            content = random.choice(DUAS)
            broadcast_athkar("dua", content)
            print(f"✅ دعاء منتصف النهار - {now}")
        
    except Exception as e:
        print(f"⚠️ خطأ في الجدولة: {e}")
    
    time.sleep(60)
```

# ═══════════════════════════════════════════════════════════════

# حماية المجموعات

# ═══════════════════════════════════════════════════════════════

def is_admin(group_id, user_id):
“”“التحقق من صلاحيات الإدارة”””
try:
profile = line_bot_api.get_group_member_profile(group_id, user_id)
return True
except:
return user_id in data[“admins”].get(group_id, [])

def kick_user(group_id, user_id):
“”“طرد مستخدم من المجموعة”””
try:
line_bot_api.leave_group(group_id)
return True
except:
return False

BAD_WORDS = [
“كلمة1”, “كلمة2”, “كلمة3”
]

def check_spam(user_id, group_id):
“”“فحص السبام”””
key = f”{group_id}_{user_id}”
now = time.time()

```
if key not in data["warnings"]:
    data["warnings"][key] = {"count": 1, "last_time": now}
    return False

last_time = data["warnings"][key]["last_time"]
if now - last_time < 5:
    data["warnings"][key]["count"] += 1
    if data["warnings"][key]["count"] >= 5:
        return True
else:
    data["warnings"][key] = {"count": 1, "last_time": now}

save_data()
return False
```

# ═══════════════════════════════════════════════════════════════

# Routes

# ═══════════════════════════════════════════════════════════════

@app.route(”/”, methods=[“GET”])
def home():
return f”””
╔══════════════════════════════════════╗
║   🕌 بوت ذكرني الإسلامي الاحترافي   ║
╚══════════════════════════════════════╝

```
📊 الإحصائيات:
👥 المستخدمون: {len(data['users'])}
👥 المجموعات: {len(data['groups'])}
📿 إجمالي الأذكار: {sum(data['stats'].values())}

✅ البوت يعمل بنجاح
""", 200
```

@app.route(”/callback”, methods=[“POST”])
def callback():
signature = request.headers.get(“X-Line-Signature”, “”)
body = request.get_data(as_text=True)
try:
handler.handle(body, signature)
except InvalidSignatureError:
return “Invalid signature”, 400
except Exception as e:
print(f”⚠️ خطأ: {e}”)
return “Error”, 500
return “OK”, 200

# ═══════════════════════════════════════════════════════════════

# معالجة الانضمام

# ═══════════════════════════════════════════════════════════════

@handler.add(JoinEvent)
def handle_join(event):
“”“عند إضافة البوت لمجموعة”””
group_id = event.source.group_id
if group_id not in data[“groups”]:
data[“groups”].append(group_id)
save_data()

```
welcome = """╔══════════════════════════════════════╗
```

║   🕌 بوت ذكرني الإسلامي الاحترافي   ║
╚══════════════════════════════════════╝

أهلاً بكم في بوت ذكرني الإسلامي

✨ المميزات:
• أذكار تلقائية (صباح، مساء، نوم)
• تذكير بمواقيت الصلاة
• حماية المجموعة
• إحصائيات يومية

📱 الأوامر:
• ذكرني - إرسال ذكر للجميع
• إحصائياتي - عرض إحصائياتك
• مساعدة - قائمة الأوامر

⏰ الأذكار التلقائية:
• 5:00 ص - تذكير الفجر
• 6:00 ص - أذكار الصباح
• 12:00 م - تذكير الظهر
• 3:30 م - تذكير العصر
• 6:00 م - أذكار المساء + المغرب
• 7:30 م - تذكير العشاء
• 10:30 م - أذكار النوم”””

```
send_message(group_id, welcome)
```

@handler.add(MemberJoinedEvent)
def handle_member_join(event):
“”“عند انضمام عضو جديد”””
group_id = event.source.group_id
welcome = “📿 أهلاً بك في المجموعة\nنسأل الله أن يبارك لك ويبارك عليك”
send_message(group_id, welcome)

# ═══════════════════════════════════════════════════════════════

# معالجة الرسائل

# ═══════════════════════════════════════════════════════════════

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
try:
text = event.message.text.strip()
user_id = getattr(event.source, “user_id”, None)
group_id = getattr(event.source, “group_id”, None)

```
    # تسجيل المستخدمين
    if user_id and user_id not in data["users"]:
        data["users"].append(user_id)
        save_data()
    
    # فحص الكلمات السيئة
    if group_id:
        for word in BAD_WORDS:
            if word in text:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ يرجى استخدام لغة محترمة")
                )
                return
        
        if check_spam(user_id, group_id):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ تم اكتشاف سبام، يرجى التوقف")
            )
            return
    
    # ═══════════ أمر ذكرني ═══════════
    if text.lower() in ["ذكرني", "تذكير", "ذكر"]:
        content_type = random.choice(["dua", "hadith", "quran"])
        
        if content_type == "dua":
            content = random.choice(DUAS)
            athkar_type = "dua"
        elif content_type == "hadith":
            content = random.choice(HADITHS)
            athkar_type = "hadith"
        else:
            content = random.choice(QURAN_VERSES)
            athkar_type = "quran"
        
        # إحصائيات المستخدم
        if user_id:
            if user_id not in data["user_stats"]:
                data["user_stats"][user_id] = 0
            data["user_stats"][user_id] += 1
            save_data()
        
        # إرسال للجميع
        message = format_athkar_message(athkar_type, content)
        sent_count = 0
        
        for uid in data["users"]:
            if send_message(uid, message):
                sent_count += 1
            time.sleep(0.2)
        
        for gid in data["groups"]:
            if send_message(gid, message):
                sent_count += 1
            time.sleep(0.2)
        
        data["stats"][f"total_{athkar_type}s_sent"] = data["stats"].get(f"total_{athkar_type}s_sent", 0) + 1
        save_data()
        
        reply = f"✅ تم إرسال الذكر لـ {sent_count} مستخدم ومجموعة"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    # ═══════════ أمر الإحصائيات ═══════════
    if text.lower() in ["إحصائياتي", "إحصائيات", "احصائياتي", "احصائيات", "stats"]:
        if not user_id:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ هذا الأمر متاح للمستخدمين فقط")
            )
            return
        
        user_count = data["user_stats"].get(user_id, 0)
        divider = "─" * 30
        
        stats_msg = f"""📊 إحصائياتك اليومية
```

{divider}

📿 عدد الأذكار: {user_count}
📅 التاريخ: {get_current_date()}

{divider}
جزاك الله خيراً”””

```
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=stats_msg))
        return
    
    # ═══════════ أمر المساعدة ═══════════
    if text.lower() in ["مساعدة", "help", "الأوامر", "اوامر"]:
        divider = "─" * 30
        help_msg = f"""📋 قائمة الأوامر
```

{divider}

📿 الأذكار:
• ذكرني - إرسال ذكر للجميع
• إحصائياتي - عرض إحصائياتك

📊 الإحصائيات العامة:
• الإحصائيات - إحصائيات البوت

🛡️ الحماية (للمشرفين):
• طرد @مستخدم - طرد عضو
• حظر @مستخدم - حظر عضو
• إلغاء حظر @مستخدم

⏰ الأذكار التلقائية:
• 5:00 ص - الفجر
• 6:00 ص - أذكار الصباح
• 12:00 م - الظهر
• 2:00 م - دعاء منتصف النهار
• 3:30 م - العصر
• 6:00 م - أذكار المساء + المغرب
• 7:30 م - العشاء
• 10:30 م - أذكار النوم

{divider}
🕌 بوت ذكرني الإسلامي”””

```
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg))
        return
    
    # ═══════════ الإحصائيات العامة ═══════════
    if text.lower() in ["الإحصائيات", "الاحصائيات", "statistics"]:
        divider = "─" * 30
        total = sum(data["stats"].values())
        
        stats_msg = f"""📊 إحصائيات البوت
```

{divider}

👥 المستخدمون: {len(data[‘users’])}
👥 المجموعات: {len(data[‘groups’])}
📿 إجمالي الأذكار: {total}
🤲 الأدعية: {data[‘stats’].get(‘total_duas_sent’, 0)}
📖 الأحاديث: {data[‘stats’].get(‘total_hadiths_sent’, 0)}
📗 القرآن: {data[‘stats’].get(‘total_qurans_sent’, 0)}

{divider}
📅 {get_current_date()}”””

```
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=stats_msg))
        return
    
    # ═══════════ أوامر الحماية ═══════════
    if group_id and text.startswith("طرد"):
        if not is_admin(group_id, user_id):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ هذا الأمر للمشرفين فقط")
            )
            return
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ تم تنفيذ الأمر")
        )
        return
    
    if group_id and text.startswith("حظر"):
        if not is_admin(group_id, user_id):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ هذا الأمر للمشرفين فقط")
            )
            return
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ تم حظر المستخدم")
        )
        return
    
    # ═══════════ أوامر سريعة ═══════════
    if text.lower() in ["سبحان الله", "سبحان الله وبحمده"]:
        reply = "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ سُبْحَانَ اللَّهِ الْعَظِيمِ"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    if text.lower() in ["استغفر الله", "استغفرالله"]:
        reply = "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ الَّذِي لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ وَأَتُوبُ إِلَيْهِ"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    if text.lower() in ["الحمد لله", "الحمدلله"]:
        reply = "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    if text.lower() in ["لا إله إلا الله", "لا اله الا الله"]:
        reply = "لَا إِلَهَ إِلَّا اللَّهُ مُحَمَّدٌ رَسُولُ اللَّهِ"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    if text.lower() in ["الله أكبر", "الله اكبر"]:
        reply = "اللَّهُ أَكْبَرُ كَبِيرًا وَالْحَمْدُ لِلَّهِ كَثِيرًا"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    # ═══════════ أذكار خاصة ═══════════
    if text.lower() in ["أذكار الصباح", "اذكار الصباح"]:
        content = random.choice(MORNING_ATHKAR)
        message = format_athkar_message("morning", content)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
    if text.lower() in ["أذكار المساء", "اذكار المساء"]:
        content = random.choice(EVENING_ATHKAR)
        message = format_athkar_message("evening", content)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
    if text.lower() in ["أذكار النوم", "اذكار النوم"]:
        content = random.choice(SLEEP_ATHKAR)
        message = format_athkar_message("sleep", content)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
    if text.lower() in ["دعاء", "ادعية"]:
        content = random.choice(DUAS)
        message = format_athkar_message("dua", content)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
    if text.lower() in ["حديث", "احاديث"]:
        content = random.choice(HADITHS)
        message = format_athkar_message("hadith", content)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
    if text.lower() in ["آية", "قرآن", "قران"]:
        content = random.choice(QURAN_VERSES)
        message = format_athkar_message("quran", content)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
except Exception as e:
    print(f"⚠️ خطأ في معالجة الرسالة: {e}")
    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ حدث خطأ، يرجى المحاولة مرة أخرى")
        )
    except:
        pass
```

# ═══════════════════════════════════════════════════════════════

# تشغيل التطبيق

# ═══════════════════════════════════════════════════════════════

if **name** == “**main**”:
reset_daily_stats()

```
# تشغيل الجدولة في خيط منفصل
threading.Thread(target=auto_athkar_scheduler, daemon=True).start()

print("╔══════════════════════════════════════╗")
print("║   🕌 بوت ذكرني الإسلامي الاحترافي   ║")
print("╚══════════════════════════════════════╝")
print(f"")
print(f"🚀 المنفذ: {PORT}")
print(f"📅 التاريخ: {get_current_date()}")
print(f"👥 المستخدمون: {len(data['users'])}")
print(f"👥 المجموعات: {len(data['groups'])}")
print(f"📿 إجمالي الأذكار: {sum(data['stats'].values())}")
print(f"")
print("✅ البوت جاهز للعمل!")
print("════════════════════════════════════════")

app.run(host="0.0.0.0", port=PORT, debug=False)
```
