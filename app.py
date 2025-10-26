import os
import json
import random
import time
import threading
import re
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
MessageEvent, TextMessage, TextSendMessage,
JoinEvent, MemberJoinedEvent, PostbackEvent
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
HELP_FILE = “help.txt”

# ═══════════════════════════════════════════════════════════════

# إدارة البيانات

# ═══════════════════════════════════════════════════════════════

def load_data():
if not os.path.exists(DATA_FILE):
return {
“users”: [],
“groups”: [],
“group_admins”: {},
“blocked_users”: [],
“warnings”: {},
“user_tasbeeh”: {},
“user_points”: {},
“current_question”: None,
“last_reset_date”: get_current_date()
}
try:
with open(DATA_FILE, “r”, encoding=“utf-8”) as f:
data = json.load(f)
# إضافة الحقول الجديدة إذا لم تكن موجودة
if “user_points” not in data:
data[“user_points”] = {}
if “current_question” not in data:
data[“current_question”] = None
return data
except:
return {
“users”: [],
“groups”: [],
“group_admins”: {},
“blocked_users”: [],
“warnings”: {},
“user_tasbeeh”: {},
“user_points”: {},
“current_question”: None,
“last_reset_date”: get_current_date()
}

def save_data():
try:
with open(DATA_FILE, “w”, encoding=“utf-8”) as f:
json.dump(data, f, ensure_ascii=False, indent=2)
except Exception as e:
print(f”⚠️ خطأ في حفظ البيانات: {e}”)

def reset_daily_counts():
current_date = get_current_date()
if data.get(“last_reset_date”) != current_date:
data[“user_tasbeeh”] = {}
data[“warnings”] = {}
data[“last_reset_date”] = current_date
save_data()
print(f”✅ إعادة تعيين العدادات اليومية - {current_date}”)

data = load_data()

# ═══════════════════════════════════════════════════════════════

# المحتوى الإسلامي

# ═══════════════════════════════════════════════════════════════

MORNING_ATHKAR = [
“أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ وَالْحَمْدُ لِلَّهِ”,
“اللَّهُمَّ بِكَ أَصْبَحْنَا وَبِكَ أَمْسَيْنَا وَبِكَ نَحْيَا وَبِكَ نَمُوتُ وَإِلَيْكَ النُّشُور”,
“أَصْبَحْنَا عَلَى فِطْرَةِ الْإِسْلَامِ وَعَلَى كَلِمَةِ الْإِخْلَاصِ وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ”,
“رَضِيتُ بِاللَّهِ رَبًّا وَبِالْإِسْلَامِ دِينًا وَبِمُحَمَّدٍ ﷺ نَبِيًّا”,
“اللَّهُمَّ إِنِّي أَصْبَحْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ وَمَلَائِكَتَكَ”,
]

EVENING_ATHKAR = [
“أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ وَالْحَمْدُ لِلَّهِ”,
“اللَّهُمَّ بِكَ أَمْسَيْنَا وَبِكَ أَصْبَحْنَا وَبِكَ نَحْيَا وَبِكَ نَمُوتُ وَإِلَيْكَ الْمَصِير”,
“أَمْسَيْنَا عَلَى فِطْرَةِ الْإِسْلَامِ وَعَلَى كَلِمَةِ الْإِخْلَاصِ وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ”,
“رَضِيتُ بِاللَّهِ رَبًّا وَبِالْإِسْلَامِ دِينًا وَبِمُحَمَّدٍ ﷺ نَبِيًّا”,
“اللَّهُمَّ إِنِّي أَمْسَيْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ وَمَلَائِكَتَكَ”,
]

SLEEP_ATHKAR = [
“بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا”,
“اللَّهُمَّ إِنَّكَ خَلَقْتَ نَفْسِي وَأَنْتَ تَوَفَّاهَا لَكَ مَمَاتُهَا وَمَحْيَاهَا”,
“اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ”,
“اللَّهُمَّ بِاسْمِكَ رَبِّي وَضَعْتُ جَنْبِي وَبِكَ أَرْفَعُهُ”,
]

DUAS = [
“اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ”,
“رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ”,
“اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ”,
“رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي”,
“اللَّهُمَّ إِنِّي أَسْأَلُكَ عِلْمًا نَافِعًا وَرِزْقًا طَيِّبًا”,
]

HADITHS = [
“مَنْ قَالَ سُبْحَانَ اللَّهِ وَبِحَمْدِهِ فِي يَوْمٍ مِائَةَ مَرَّةٍ حُطَّتْ خَطَايَاهُ”,
“الْمُؤْمِنُ الْقَوِيُّ خَيْرٌ وَأَحَبُّ إِلَى اللَّهِ مِنَ الْمُؤْمِنِ الضَّعِيفِ”,
“مَنْ كَانَ يُؤْمِنُ بِاللَّهِ وَالْيَوْمِ الْآخِرِ فَلْيَقُلْ خَيْرًا أَوْ لِيَصْمُتْ”,
“الْكَلِمَةُ الطَّيِّبَةُ صَدَقَةٌ”,
“أَحَبُّ الْأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ”,
]

QURAN_VERSES = [
“إِنَّ مَعَ الْعُسْرِ يُسْرًا”,
“فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ”,
“وَلَا تَيْأَسُوا مِن رَّوْحِ اللَّهِ”,
“إِنَّ اللَّهَ مَعَ الصَّابِرِينَ”,
“وَمَن يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ”,
]

# ═══════════════════════════════════════════════════════════════

# سورة اليوم

# ═══════════════════════════════════════════════════════════════

DAILY_SURAHS = [
{
“name”: “الفاتحة”,
“number”: 1,
“ayat”: 7,
“fadl”: “أعظم سورة في القرآن، تُقرأ في كل ركعة”,
“theme”: “الحمد لله والدعاء بالهداية”
},
{
“name”: “الإخلاص”,
“number”: 112,
“ayat”: 4,
“fadl”: “تعدل ثلث القرآن”,
“theme”: “توحيد الله وتنزيهه”
},
{
“name”: “الفلق”,
“number”: 113,
“ayat”: 5,
“fadl”: “من المعوذتين، حماية من الشر”,
“theme”: “الاستعاذة من شر المخلوقات”
},
{
“name”: “الناس”,
“number”: 114,
“ayat”: 6,
“fadl”: “من المعوذتين، حماية من الوسواس”,
“theme”: “الاستعاذة من شر الشيطان”
},
{
“name”: “الكوثر”,
“number”: 108,
“ayat”: 3,
“fadl”: “أقصر سورة في القرآن”,
“theme”: “النعم الإلهية والصلاة”
},
{
“name”: “الإخلاص”,
“number”: 112,
“ayat”: 4,
“fadl”: “من قرأها عشر مرات بنى الله له بيتاً في الجنة”,
“theme”: “وحدانية الله”
},
{
“name”: “الكافرون”,
“number”: 109,
“ayat”: 6,
“fadl”: “تعدل ربع القرآن، براءة من الشرك”,
“theme”: “البراءة من الكفر”
},
{
“name”: “المسد”,
“number”: 111,
“ayat”: 5,
“fadl”: “فيها عقوبة أبي لهب”,
“theme”: “عاقبة الكافرين”
},
{
“name”: “النصر”,
“number”: 110,
“ayat”: 3,
“fadl”: “آخر سورة نزلت كاملة”,
“theme”: “فتح مكة والتسبيح”
},
{
“name”: “الماعون”,
“number”: 107,
“ayat”: 7,
“fadl”: “تحذير من المنافقين”,
“theme”: “الصلاة والإحسان”
},
{
“name”: “قريش”,
“number”: 106,
“ayat”: 4,
“fadl”: “تذكير بنعم الله على قريش”,
“theme”: “شكر النعم”
},
{
“name”: “الفيل”,
“number”: 105,
“ayat”: 5,
“fadl”: “قصة أصحاب الفيل”,
“theme”: “قدرة الله ونصره”
},
{
“name”: “الهمزة”,
“number”: 104,
“ayat”: 9,
“fadl”: “تحذير من الغيبة والنميمة”,
“theme”: “ذم الهمز واللمز”
},
{
“name”: “العصر”,
“number”: 103,
“ayat”: 3,
“fadl”: “قال الشافعي: لو تدبر الناس هذه السورة لكفتهم”,
“theme”: “الإيمان والعمل الصالح”
},
{
“name”: “التكاثر”,
“number”: 102,
“ayat”: 8,
“fadl”: “تحذير من الانشغال بالدنيا”,
“theme”: “زيارة القبور والآخرة”
},
{
“name”: “القارعة”,
“number”: 101,
“ayat”: 11,
“fadl”: “وصف يوم القيامة”,
“theme”: “أهوال يوم القيامة”
},
{
“name”: “العاديات”,
“number”: 100,
“ayat”: 11,
“fadl”: “القسم بالخيل”,
“theme”: “كفران الإنسان للنعم”
},
{
“name”: “الزلزلة”,
“number”: 99,
“ayat”: 8,
“fadl”: “تعدل نصف القرآن”,
“theme”: “زلزلة الأرض يوم القيامة”
},
{
“name”: “القدر”,
“number”: 97,
“ayat”: 5,
“fadl”: “فضل ليلة القدر”,
“theme”: “ليلة القدر خير من ألف شهر”
},
{
“name”: “التين”,
“number”: 95,
“ayat”: 8,
“fadl”: “القسم بالتين والزيتون”,
“theme”: “خلق الإنسان في أحسن تقويم”
},
{
“name”: “الشرح”,
“number”: 94,
“ayat”: 8,
“fadl”: “تذكير بنعم الله على النبي ﷺ”,
“theme”: “مع العسر يسراً”
},
{
“name”: “الضحى”,
“number”: 93,
“ayat”: 11,
“fadl”: “تطمين النبي ﷺ”,
“theme”: “نعم الله على النبي”
},
{
“name”: “الليل”,
“number”: 92,
“ayat”: 21,
“fadl”: “القسم بالليل والنهار”,
“theme”: “الجزاء على الأعمال”
},
{
“name”: “الشمس”,
“number”: 91,
“ayat”: 15,
“fadl”: “القسم بالشمس والقمر”,
“theme”: “تزكية النفس”
},
{
“name”: “البلد”,
“number”: 90,
“ayat”: 20,
“fadl”: “القسم بمكة المكرمة”,
“theme”: “صعوبة طريق الخير”
}
]

# ═══════════════════════════════════════════════════════════════

# الأسئلة الدينية

# ═══════════════════════════════════════════════════════════════

RELIGIOUS_QUESTIONS = [
{
“question”: “كم عدد أركان الإسلام؟”,
“options”: [“أ) 4”, “ب) 5”, “ج) 6”, “د) 7”],
“correct”: “ب”,
“explanation”: “أركان الإسلام خمسة: الشهادتان، الصلاة، الزكاة، الصوم، الحج”
},
{
“question”: “كم عدد أركان الإيمان؟”,
“options”: [“أ) 5”, “ب) 6”, “ج) 7”, “د) 8”],
“correct”: “ب”,
“explanation”: “أركان الإيمان ستة: الإيمان بالله، الملائكة، الكتب، الرسل، اليوم الآخر، القدر”
},
{
“question”: “كم عدد الصلوات المفروضة في اليوم؟”,
“options”: [“أ) 3”, “ب) 4”, “ج) 5”, “د) 6”],
“correct”: “ج”,
“explanation”: “الصلوات الخمس: الفجر، الظهر، العصر، المغرب، العشاء”
},
{
“question”: “في أي شهر فُرض الصيام؟”,
“options”: [“أ) شعبان”, “ب) رمضان”, “ج) رجب”, “د) ذو القعدة”],
“correct”: “ب”,
“explanation”: “شهر رمضان المبارك هو شهر الصيام”
},
{
“question”: “كم عدد سور القرآن الكريم؟”,
“options”: [“أ) 110”, “ب) 112”, “ج) 114”, “د) 116”],
“correct”: “ج”,
“explanation”: “القرآن الكريم يحتوي على 114 سورة”
},
{
“question”: “ما أطول سورة في القرآن؟”,
“options”: [“أ) البقرة”, “ب) آل عمران”, “ج) النساء”, “د) الأعراف”],
“correct”: “أ”,
“explanation”: “سورة البقرة هي أطول سورة في القرآن بـ 286 آية”
},
{
“question”: “ما أقصر سورة في القرآن؟”,
“options”: [“أ) الإخلاص”, “ب) الكوثر”, “ج) النصر”, “د) الفلق”],
“correct”: “ب”,
“explanation”: “سورة الكوثر هي أقصر سورة بـ 3 آيات”
},
{
“question”: “من هو خاتم الأنبياء؟”,
“options”: [“أ) عيسى”, “ب) موسى”, “ج) محمد”, “د) إبراهيم”],
“correct”: “ج”,
“explanation”: “النبي محمد ﷺ هو خاتم الأنبياء والمرسلين”
},
{
“question”: “في أي عام هاجر النبي ﷺ؟”,
“options”: [“أ) السنة 1 هـ”, “ب) السنة 2 هـ”, “ج) السنة 3 هـ”, “د) السنة 10 هـ”],
“correct”: “أ”,
“explanation”: “هجرة النبي من مكة إلى المدينة كانت في السنة الأولى للهجرة”
},
{
“question”: “كم عدد أولي العزم من الرسل؟”,
“options”: [“أ) 3”, “ب) 4”, “ج) 5”, “د) 6”],
“correct”: “ج”,
“explanation”: “أولو العزم: نوح، إبراهيم، موسى، عيسى، محمد عليهم السلام”
},
{
“question”: “ما أول ما يُحاسب عليه العبد يوم القيامة؟”,
“options”: [“أ) الزكاة”, “ب) الصيام”, “ج) الصلاة”, “د) الحج”],
“correct”: “ج”,
“explanation”: “الصلاة أول ما يُحاسب عليه العبد يوم القيامة”
},
{
“question”: “كم عدد التكبيرات في صلاة العيد؟”,
“options”: [“أ) 6 و 5”, “ب) 7 و 5”, “ج) 7 و 6”, “د) 8 و 6”],
“correct”: “ب”,
“explanation”: “7 تكبيرات في الركعة الأولى و 5 في الثانية”
},
{
“question”: “ما معنى لا إله إلا الله؟”,
“options”: [“أ) الله موجود”, “ب) لا معبود بحق إلا الله”, “ج) الله واحد”, “د) الله قادر”],
“correct”: “ب”,
“explanation”: “معناها: لا معبود بحق إلا الله وحده”
},
{
“question”: “من هو أول من آمن من الرجال؟”,
“options”: [“أ) عمر بن الخطاب”, “ب) أبو بكر الصديق”, “ج) عثمان بن عفان”, “د) علي بن أبي طالب”],
“correct”: “ب”,
“explanation”: “أبو بكر الصديق رضي الله عنه أول من آمن من الرجال”
},
{
“question”: “من هي أول من آمنت من النساء؟”,
“options”: [“أ) عائشة”, “ب) فاطمة”, “ج) خديجة”, “د) حفصة”],
“correct”: “ج”,
“explanation”: “خديجة بنت خويلد رضي الله عنها أول من آمن من النساء”
},
{
“question”: “كم مرة ذُكرت كلمة ‘الجنة’ في القرآن تقريباً؟”,
“options”: [“أ) 50”, “ب) 70”, “ج) 100”, “د) 140”],
“correct”: “ج”,
“explanation”: “ذُكرت الجنة في القرآن حوالي 100 مرة”
},
{
“question”: “ما السورة التي تُسمى قلب القرآن؟”,
“options”: [“أ) البقرة”, “ب) آل عمران”, “ج) يس”, “د) الكهف”],
“correct”: “ج”,
“explanation”: “سورة يس تُسمى قلب القرآن”
},
{
“question”: “كم سنة دعا نوح عليه السلام قومه؟”,
“options”: [“أ) 500 سنة”, “ب) 750 سنة”, “ج) 850 سنة”, “د) 950 سنة”],
“correct”: “د”,
“explanation”: “دعا نوح قومه 950 سنة”
},
{
“question”: “ما اسم الملَك الموكل بالنفخ في الصور؟”,
“options”: [“أ) جبريل”, “ب) ميكائيل”, “ج) إسرافيل”, “د) عزرائيل”],
“correct”: “ج”,
“explanation”: “إسرافيل عليه السلام الموكل بالنفخ في الصور”
},
{
“question”: “كم عدد أبواب الجنة؟”,
“options”: [“أ) 7”, “ب) 8”, “ج) 9”, “د) 10”],
“correct”: “ب”,
“explanation”: “للجنة 8 أبواب”
}
]

# ═══════════════════════════════════════════════════════════════

# حماية المجموعات

# ═══════════════════════════════════════════════════════════════

BAD_WORDS = [
“كلمة1”, “كلمة2”, “كلمة3”,  # ضع الكلمات السيئة هنا
]

def check_bad_words(text):
“”“فحص الكلمات السيئة”””
text_lower = text.lower()
for word in BAD_WORDS:
if word in text_lower:
return True
return False

def check_spam(user_id, group_id):
“”“فحص السبام - 5 رسائل في 10 ثواني”””
key = f”{group_id}_{user_id}”
now = time.time()

```
if key not in data["warnings"]:
    data["warnings"][key] = {"count": 1, "last_time": now, "times": [now]}
    return False

# تنظيف الأوقات القديمة (أكثر من 10 ثواني)
data["warnings"][key]["times"] = [t for t in data["warnings"][key]["times"] if now - t < 10]
data["warnings"][key]["times"].append(now)

if len(data["warnings"][key]["times"]) >= 5:
    return True

save_data()
return False
```

def check_links(text):
“”“فحص الروابط المشبوهة”””
url_pattern = re.compile(r’http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+’)
return bool(url_pattern.search(text))

def is_admin(group_id, user_id):
“”“التحقق من صلاحيات الإدارة”””
return user_id in data[“group_admins”].get(group_id, [])

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

def format_message(title, content):
“”“تنسيق الرسائل بشكل أنيق”””
divider = “─” * 30
return f”{title}\n{divider}\n\n{content}\n\n{divider}”

def broadcast_message(title, content):
“”“إرسال رسالة لجميع المستخدمين والمجموعات”””
message = format_message(title, content)
sent_count = 0

```
for uid in data["users"]:
    if uid not in data["blocked_users"]:
        if send_message(uid, message):
            sent_count += 1
        time.sleep(0.3)

for gid in data["groups"]:
    if send_message(gid, message):
        sent_count += 1
    time.sleep(0.3)

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
“surah”: False,
“question”: False
}

```
while True:
    try:
        now = get_current_time()
        current_date = now.strftime("%Y-%m-%d")
        hour = now.hour
        minute = now.minute
        
        if last_check_date != current_date:
            reset_daily_counts()
            sent_today = {k: False for k in sent_today}
            last_check_date = current_date
        
        # أذكار الصباح - 6:00 ص
        if hour == 6 and minute == 0 and not sent_today["morning"]:
            content = random.choice(MORNING_ATHKAR)
            broadcast_message("☀️ أذكار الصباح", content)
            sent_today["morning"] = True
            print(f"✅ أذكار الصباح - {now}")
        
        # سورة اليوم - 9:00 ص
        elif hour == 9 and minute == 0 and not sent_today["surah"]:
            surah = random.choice(DAILY_SURAHS)
            content = f"""📖 سورة {surah['name']}
```

رقم السورة: {surah[‘number’]}
عدد الآيات: {surah[‘ayat’]}

💎 فضلها:
{surah[‘fadl’]}

📝 موضوعها:
{surah[‘theme’]}

ننصح بقراءتها وحفظها”””
broadcast_message(“📗 سورة اليوم”, content)
sent_today[“surah”] = True
print(f”✅ سورة اليوم - {now}”)

```
        # السؤال الديني - 2:00 م
        elif hour == 14 and minute == 0 and not sent_today["question"]:
            q = random.choice(RELIGIOUS_QUESTIONS)
            options_text = "\n".join(q['options'])
            content = f"""{q['question']}
```

{options_text}

أرسل الإجابة (أ، ب، ج، أو د)
مثال: أ”””
broadcast_message(“❓ سؤال اليوم”, content)

```
            # حفظ السؤال الحالي
            data["current_question"] = q
            save_data()
            
            sent_today["question"] = True
            print(f"✅ سؤال اليوم - {now}")
        
        # أذكار المساء - 6:00 م
        elif hour == 18 and minute == 0 and not sent_today["evening"]:
            content = random.choice(EVENING_ATHKAR)
            broadcast_message("🌙 أذكار المساء", content)
            sent_today["evening"] = True
            print(f"✅ أذكار المساء - {now}")
        
        # أذكار النوم - 10:30 م
        elif hour == 22 and minute == 30 and not sent_today["sleep"]:
            content = random.choice(SLEEP_ATHKAR)
            broadcast_message("💤 أذكار النوم", content)
            sent_today["sleep"] = True
            print(f"✅ أذكار النوم - {now}")
        
    except Exception as e:
        print(f"⚠️ خطأ في الجدولة: {e}")
    
    time.sleep(60)
```

# ═══════════════════════════════════════════════════════════════

# Routes

# ═══════════════════════════════════════════════════════════════

@app.route(”/”, methods=[“GET”])
def home():
return f”””
🕌 بوت ذكرني الإسلامي

```
المستخدمون: {len(data['users'])}
المجموعات: {len(data['groups'])}

✅ يعمل بنجاح
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
welcome = """🕌 بوت ذكرني الإسلامي
```

─────────────────────────────

مرحباً بكم

المميزات:
• أذكار تلقائية (صباح، مساء، نوم)
• سورة اليوم مع فضلها
• سؤال ديني يومي
• نظام نقاط تشجيعي
• حماية المجموعة من السبام

الأوامر:
• مساعدة - عرض المساعدة
• ذكرني - إرسال ذكر للجميع
• عدد - عرض التسبيحات والنقاط
• سورة - اقتراح سورة للقراءة
• سؤال - سؤال ديني

الأذكار التلقائية:
• 6:00 ص - أذكار الصباح
• 9:00 ص - سورة اليوم
• 2:00 م - سؤال اليوم
• 6:00 م - أذكار المساء
• 10:30 م - أذكار النوم”””

```
send_message(group_id, welcome)
```

@handler.add(MemberJoinedEvent)
def handle_member_join(event):
“”“عند انضمام عضو جديد”””
group_id = event.source.group_id
welcome = “”
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
    # تسجيل المستخدمين تلقائياً
    if user_id and user_id not in data["users"]:
        data["users"].append(user_id)
        save_data()
    
    # ═══════════ حماية المجموعات ═══════════
    if group_id:
        # فحص المحظورين
        if user_id in data["blocked_users"]:
            return
        
        # فحص الكلمات السيئة
        if check_bad_words(text):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ يرجى استخدام لغة محترمة")
            )
            return
        
        # فحص السبام
        if check_spam(user_id, group_id):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ تم اكتشاف سبام، يرجى التوقف")
            )
            return
        
        # فحص الروابط (إلا للمشرفين)
        if check_links(text) and not is_admin(group_id, user_id):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ ممنوع إرسال روابط بدون إذن")
            )
            return
    
    # ═══════════ أمر المساعدة ═══════════
    if text.lower() in ["مساعدة", "help"]:
        try:
            with open(HELP_FILE, "r", encoding="utf-8") as f:
                help_text = f.read()
        except:
            help_text = """📋 أوامر البوت
```

─────────────────────────────

📿 الأذكار:
• ذكرني - إرسال ذكر
• عدد - عرض عدد التسبيحات اليومية

🕌 بوت ذكرني الإسلامي”””

```
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return
    
    # ═══════════ أمر ذكرني ═══════════
    if text.lower() in ["ذكرني", "تذكير", "ذكر"]:
        content_type = random.choice(["dua", "hadith", "quran"])
        
        if content_type == "dua":
            title = "🤲 دعاء"
            content = random.choice(DUAS)
        elif content_type == "hadith":
            title = "📿 حديث شريف"
            content = random.choice(HADITHS)
        else:
            title = "📖 قرآن كريم"
            content = random.choice(QURAN_VERSES)
        
        # زيادة عداد التسبيح
        if user_id:
            data["user_tasbeeh"][user_id] = data["user_tasbeeh"].get(user_id, 0) + 1
            save_data()
        
        # إرسال للجميع
        sent_count = broadcast_message(title, content)
        
        reply = f"✅ تم الإرسال لـ {sent_count} مستخدم ومجموعة"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    # ═══════════ أمر عدد التسبيحات ═══════════
    if text.lower() in ["عدد", "العدد", "التسبيحات"]:
        if not user_id:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ هذا الأمر للمستخدمين فقط")
            )
            return
        
        count = data["user_tasbeeh"].get(user_id, 0)
        divider = "─" * 30
        
        message = f"""📊 عدد التسبيحات اليومية
```

{divider}

📿 عدد المرات: {count}
📅 التاريخ: {get_current_date()}

{divider}
جزاك الله خيراً”””

```
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        return
    
    # ═══════════ أوامر الإدارة ═══════════
    if group_id and text.lower().startswith("مشرف"):
        # إضافة مشرف
        parts = text.split()
        if len(parts) > 1:
            if group_id not in data["group_admins"]:
                data["group_admins"][group_id] = []
            if user_id not in data["group_admins"][group_id]:
                data["group_admins"][group_id].append(user_id)
                save_data()
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="✅ تم إضافة المشرف")
                )
        return
    
    if group_id and text.lower().startswith("حظر") and is_admin(group_id, user_id):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ تم حظر المستخدم")
        )
        return
    
except Exception as e:
    print(f"⚠️ خطأ في معالجة الرسالة: {e}")
```

# ═══════════════════════════════════════════════════════════════

# تشغيل التطبيق

# ═══════════════════════════════════════════════════════════════

if **name** == “**main**”:
reset_daily_counts()

```
# تشغيل الجدولة
threading.Thread(target=auto_athkar_scheduler, daemon=True).start()

print("╔══════════════════════════════════════╗")
print("║      🕌 بوت ذكرني الإسلامي          ║")
print("╚══════════════════════════════════════╝")
print(f"")
print(f"🚀 المنفذ: {PORT}")
print(f"👥 المستخدمون: {len(data['users'])}")
print(f"👥 المجموعات: {len(data['groups'])}")
print(f"")
print("✅ البوت جاهز!")

app.run(host="0.0.0.0", port=PORT, debug=False)
```
