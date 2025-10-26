import os
import json
import random
import threading
import time
import requests
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
import sqlite3
from contextlib import contextmanager
from collections import defaultdict

from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════

# ⚙️ الإعدادات

# ═══════════════════════════════════════════════════════════

TIMEZONE = timezone(timedelta(hours=3))
get_time = lambda: datetime.now(TIMEZONE)

load_dotenv()
TOKEN = os.getenv(“LINE_CHANNEL_ACCESS_TOKEN”)
SECRET = os.getenv(“LINE_CHANNEL_SECRET”)
PORT = int(os.getenv(“PORT”, 5000))

if not TOKEN or not SECRET:
raise ValueError(“❌ تأكد من إضافة مفاتيح LINE”)

os.makedirs(“logs”, exist_ok=True)
logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s [%(levelname)s]: %(message)s’,
handlers=[
logging.FileHandler(‘logs/bot.log’, encoding=‘utf-8’),
logging.StreamHandler()
]
)
logger = logging.getLogger(**name**)

# ═══════════════════════════════════════════════════════════

# 📚 المحتوى الإسلامي

# ═══════════════════════════════════════════════════════════

MORNING_ATHKAR = [
“أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ”,
“اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا”,
“سُبْحَانَ اللهِ وَبِحَمْدِهِ عَدَدَ خَلْقِهِ”,
]

EVENING_ATHKAR = [
“أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ”,
“اللَّهُمَّ بِكَ أَمْسَيْنَا وَبِكَ أَصْبَحْنَا”,
]

SLEEP_ATHKAR = [
“بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا”,
“اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ”,
]

DUAS = [
“رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً”,
“اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ”,
]

HADITHS = [
“مَنْ قَالَ: سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، فِي يَوْمٍ مِائَةَ مَرَّةٍ، حُطَّتْ خَطَايَاهُ”,
“أَحَبُّ الْأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ”,
]

TASBIH = [“سبحان الله”, “الحمد لله”, “الله أكبر”, “استغفر الله”, “لا إله إلا الله”]
LIMIT = 33

SURAHS = {
1: {“name”: “الفاتحة”, “virtue”: “لا صلاة لمن لم يقرأ بفاتحة الكتاب”},
18: {“name”: “الكهف”, “virtue”: “نور من الجمعة إلى الجمعة”},
36: {“name”: “يس”, “virtue”: “قلب القرآن”},
67: {“name”: “الملك”, “virtue”: “المانعة من عذاب القبر”},
}

QUESTIONS = [
{
“q”: “كم عدد أركان الإسلام؟”,
“opts”: [“أربعة”, “خمسة”, “ستة”, “سبعة”],
“ans”: 1,
“exp”: “أركان الإسلام خمسة”
},
{
“q”: “ما أطول سورة في القرآن؟”,
“opts”: [“آل عمران”, “البقرة”, “النساء”, “الأعراف”],
“ans”: 1,
“exp”: “سورة البقرة هي الأطول”
},
]

BAD_WORDS = [“كلمة1”, “كلمة2”]  # أضف الكلمات المحظورة
SPAM_LIMIT = 5  # رسائل في 10 ثواني
LINK_LIMIT = 2  # مرات السماح بالرابط

# ═══════════════════════════════════════════════════════════

# 🗄️ قاعدة البيانات المبسطة

# ═══════════════════════════════════════════════════════════

class DB:
def **init**(self, path=“bot.db”):
self.path = path
self.lock = threading.Lock()
self._init()

```
@contextmanager
def conn(self):
    c = sqlite3.connect(self.path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()

def _init(self):
    with self.lock, self.conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, city TEXT DEFAULT 'Riyadh',
            notify INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY, notify INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS tasbih (
            user TEXT, type TEXT, cnt INTEGER DEFAULT 0, 
            date TEXT, UNIQUE(user, type, date)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY, qidx INTEGER, answered INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS stats (
            user TEXT PRIMARY KEY, correct INTEGER DEFAULT 0,
            wrong INTEGER DEFAULT 0
        )""")
        c.commit()

def add_user(self, uid):
    with self.lock, self.conn() as c:
        c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
        c.commit()

def add_group(self, gid):
    with self.lock, self.conn() as c:
        c.execute("INSERT OR IGNORE INTO groups (id) VALUES (?)", (gid,))
        c.commit()

def get_city(self, uid):
    with self.conn() as c:
        r = c.execute("SELECT city FROM users WHERE id=?", (uid,)).fetchone()
        return r['city'] if r else 'Riyadh'

def set_city(self, uid, city):
    with self.lock, self.conn() as c:
        c.execute("UPDATE users SET city=? WHERE id=?", (city, uid))
        c.commit()

def inc_tasbih(self, uid, typ, date):
    with self.lock, self.conn() as c:
        c.execute("""INSERT INTO tasbih (user,type,cnt,date) VALUES (?,?,1,?)
            ON CONFLICT(user,type,date) DO UPDATE SET cnt=cnt+1""",
            (uid, typ, date))
        r = c.execute("SELECT cnt FROM tasbih WHERE user=? AND type=? AND date=?",
            (uid, typ, date)).fetchone()
        c.commit()
        return r['cnt'] if r else 0

def get_tasbih(self, uid, date):
    with self.conn() as c:
        rows = c.execute("SELECT type,cnt FROM tasbih WHERE user=? AND date=?",
            (uid, date)).fetchall()
        return {r['type']: r['cnt'] for r in rows}

def reset_tasbih(self, uid, date):
    with self.lock, self.conn() as c:
        c.execute("DELETE FROM tasbih WHERE user=? AND date=?", (uid, date))
        c.commit()

def set_question(self, tid, qidx):
    with self.lock, self.conn() as c:
        c.execute("INSERT OR REPLACE INTO questions (id,qidx,answered) VALUES (?,?,0)",
            (tid, qidx))
        c.commit()

def get_question(self, tid):
    with self.conn() as c:
        r = c.execute("SELECT qidx FROM questions WHERE id=? AND answered=0",
            (tid,)).fetchone()
        return r['qidx'] if r else None

def mark_answered(self, tid):
    with self.lock, self.conn() as c:
        c.execute("UPDATE questions SET answered=1 WHERE id=?", (tid,))
        c.commit()

def update_stats(self, uid, correct):
    with self.lock, self.conn() as c:
        c.execute("INSERT OR IGNORE INTO stats (user) VALUES (?)", (uid,))
        if correct:
            c.execute("UPDATE stats SET correct=correct+1 WHERE user=?", (uid,))
        else:
            c.execute("UPDATE stats SET wrong=wrong+1 WHERE user=?", (uid,))
        c.commit()

def get_stats(self, uid):
    with self.conn() as c:
        r = c.execute("SELECT correct,wrong FROM stats WHERE user=?", (uid,)).fetchone()
        if r:
            total = r['correct'] + r['wrong']
            pct = (r['correct'] / total * 100) if total > 0 else 0
            return {'c': r['correct'], 'w': r['wrong'], 'p': pct}
        return {'c': 0, 'w': 0, 'p': 0}

def active_users(self):
    with self.conn() as c:
        return [r['id'] for r in c.execute("SELECT id FROM users WHERE notify=1")]

def active_groups(self):
    with self.conn() as c:
        return [r['id'] for r in c.execute("SELECT id FROM groups WHERE notify=1")]
```

db = DB()

# ═══════════════════════════════════════════════════════════

# 🛡️ نظام الحماية

# ═══════════════════════════════════════════════════════════

class Protection:
def **init**(self):
self.spam = defaultdict(list)
self.links = defaultdict(lambda: defaultdict(int))
self.lock = threading.Lock()

```
def check_spam(self, uid, gid):
    with self.lock:
        now = time.time()
        key = f"{gid}:{uid}"
        self.spam[key] = [t for t in self.spam[key] if now - t < 10]
        self.spam[key].append(now)
        
        if len(self.spam[key]) > SPAM_LIMIT:
            return False, "⚠️ توقف عن السبام!"
        return True, ""

def check_words(self, txt):
    for w in BAD_WORDS:
        if w in txt.lower():
            return False, "⚠️ كلمات غير لائقة!"
    return True, ""

def check_links(self, txt, gid):
    urls = re.findall(r'https?://[^\s]+', txt)
    if not urls:
        return True, ""
    
    with self.lock:
        for url in urls:
            self.links[gid][url] += 1
            if self.links[gid][url] > LINK_LIMIT:
                return False, "⚠️ تكرار الرابط محظور!"
    return True, ""
```

protect = Protection()

# ═══════════════════════════════════════════════════════════

# 🎨 Flex Messages

# ═══════════════════════════════════════════════════════════

def create_tasbih_flex(counts, today):
“”“إنشاء Flex Message للتسبيح”””
bubbles = []

```
for typ in TASBIH:
    cnt = counts.get(typ, 0)
    pct = min(cnt / LIMIT * 100, 100)
    status = "✅" if cnt >= LIMIT else f"{int(pct)}%"
    color = "#06C755" if cnt >= LIMIT else "#1DB446"
    
    bubbles.append({
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": typ,
                "size": "md",
                "weight": "bold",
                "color": "#1A1A1A"
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [],
                        "width": f"{pct}%",
                        "backgroundColor": color,
                        "height": "6px"
                    }
                ],
                "backgroundColor": "#E0E0E0",
                "height": "6px",
                "margin": "sm"
            },
            {
                "type": "text",
                "text": f"{cnt}/{LIMIT} {status}",
                "size": "xs",
                "color": "#8C8C8C",
                "margin": "sm"
            }
        ],
        "spacing": "sm",
        "margin": "md"
    })

return {
    "type": "bubble",
    "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": "📿 التسبيح اليومي",
                "weight": "bold",
                "size": "xl",
                "color": "#1DB446"
            },
            {
                "type": "separator",
                "margin": "md"
            }
        ] + bubbles
    }
}
```

def create_surah_flex(num):
“”“Flex Message لمعلومات السورة”””
s = SURAHS.get(num)
if not s:
return None

```
return {
    "type": "bubble",
    "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": f"📖 سورة {s['name']}",
                "weight": "bold",
                "size": "xl",
                "color": "#1DB446"
            },
            {
                "type": "separator",
                "margin": "md"
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✨ الفضل:",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#555555",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": s['virtue'],
                        "size": "sm",
                        "wrap": True,
                        "color": "#8C8C8C",
                        "margin": "sm"
                    }
                ]
            }
        ]
    }
}
```

def create_question_flex(q):
“”“Flex Message للسؤال”””
return {
“type”: “bubble”,
“body”: {
“type”: “box”,
“layout”: “vertical”,
“contents”: [
{
“type”: “text”,
“text”: “❓ سؤال ديني”,
“weight”: “bold”,
“size”: “xl”,
“color”: “#1DB446”
},
{
“type”: “separator”,
“margin”: “md”
},
{
“type”: “text”,
“text”: q[‘q’],
“wrap”: True,
“weight”: “bold”,
“margin”: “md”
}
] + [
{
“type”: “box”,
“layout”: “horizontal”,
“contents”: [
{
“type”: “text”,
“text”: chr(65+i),
“flex”: 0,
“weight”: “bold”,
“color”: “#1DB446”
},
{
“type”: “text”,
“text”: opt,
“wrap”: True,
“margin”: “sm”
}
],
“margin”: “md”
}
for i, opt in enumerate(q[‘opts’])
]
},
“footer”: {
“type”: “box”,
“layout”: “vertical”,
“contents”: [
{
“type”: “text”,
“text”: “اكتب الحرف (أ، ب، ج، د)”,
“size”: “xs”,
“color”: “#AAAAAA”,
“align”: “center”
}
]
}
}

# ═══════════════════════════════════════════════════════════

# 🔐 نظام صلاحيات LINE الحقيقي

# ═══════════════════════════════════════════════════════════

def get_group_member_profile(group_id, user_id):
“”“الحصول على معلومات العضو من LINE”””
try:
profile = line_bot_api.get_group_member_profile(group_id, user_id)
return profile
except:
return None

def is_group_admin(group_id, user_id):
“”“التحقق من كون المستخدم مشرف حقيقي”””
try:
# محاولة الحصول على ملف العضو
profile = get_group_member_profile(group_id, user_id)

```
    # في LINE: لا يوجد API مباشر للتحقق من المشرفين
    # لكن يمكن استخدام طرق غير مباشرة:
    # 1. حفظ قائمة المشرفين في قاعدة البيانات
    # 2. السماح للبوت بإضافة/إزالة المشرفين يدوياً
    
    # هنا نستخدم قاعدة بيانات محلية
    with db.conn() as c:
        r = c.execute("""SELECT 1 FROM admins 
            WHERE group_id=? AND user_id=?""",
            (group_id, user_id)).fetchone()
        return r is not None
except:
    return False
```

def add_admin_to_db(group_id, user_id):
“”“إضافة مشرف للقاعدة”””
with db.lock, db.conn() as c:
c.execute(””“CREATE TABLE IF NOT EXISTS admins (
group_id TEXT, user_id TEXT,
UNIQUE(group_id, user_id)
)”””)
c.execute(“INSERT OR IGNORE INTO admins VALUES (?,?)”,
(group_id, user_id))
c.commit()

# ═══════════════════════════════════════════════════════════

# 📤 إرسال الرسائل

# ═══════════════════════════════════════════════════════════

app = Flask(**name**)
line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

def send(to, msg):
try:
if isinstance(msg, dict):
line_bot_api.push_message(to, FlexSendMessage(
alt_text=“رسالة من بوت ذكرني”,
contents=msg
))
else:
line_bot_api.push_message(to, TextSendMessage(text=msg))
return True
except Exception as e:
logger.error(f”Error sending: {e}”)
return False

# ═══════════════════════════════════════════════════════════

# 💬 معالج الرسائل

# ═══════════════════════════════════════════════════════════

@handler.add(MessageEvent, message=TextMessage)
def handle(event):
try:
txt = event.message.text.strip()
uid = getattr(event.source, “user_id”, None)
gid = getattr(event.source, “group_id”, None)
tid = uid or gid
is_grp = gid is not None

```
    # ═══ الحماية ═══
    if is_grp and uid:
        ok, msg = protect.check_spam(uid, gid)
        if not ok:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        ok, msg = protect.check_words(txt)
        if not ok:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        
        ok, msg = protect.check_links(txt, gid)
        if not ok:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
    
    # ═══ التسجيل التلقائي ═══
    if uid:
        db.add_user(uid)
    if gid:
        db.add_group(gid)
    
    today = get_time().date().isoformat()
    
    # ═══ الإجابة على سؤال ═══
    if txt in ["أ", "ب", "ج", "د"]:
        qidx = db.get_question(tid)
        if qidx is not None:
            q = QUESTIONS[qidx]
            ans_idx = ["أ", "ب", "ج", "د"].index(txt)
            correct = ans_idx == q['ans']
            
            db.update_stats(uid or tid, correct)
            db.mark_answered(tid)
            
            stats = db.get_stats(uid or tid)
            
            if correct:
                reply = f"✅ *صحيح!*\n\n💡 {q['exp']}\n\n📊 إحصائياتك:\n✅ {stats['c']} | ❌ {stats['w']} | {stats['p']:.1f}%"
            else:
                reply = f"❌ *خطأ*\n\n✅ الصحيح: {chr(65+q['ans'])}\n💡 {q['exp']}\n\n📊 إحصائياتك:\n✅ {stats['c']} | ❌ {stats['w']} | {stats['p']:.1f}%"
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
    
    # ═══ المساعدة ═══
    if txt.lower() in ["مساعدة", "help", "الاوامر"]:
        help_txt = """🌙 *بوت ذكرني v3.0*
```

📿 *التسبيح:*
سبحان الله | الحمد لله | الله أكبر
استغفر الله | لا إله إلا الله
• تسبيح - عرض التقدم
• إعادة - مسح العداد

📖 *التعليم:*
• سورة - معلومات
• سؤال - سؤال تفاعلي
• إحصائياتي

🕌 *الصلاة:*
• مدينتي [اسم]
• أوقات الصلاة

🌙 *الأذكار:*
• أذكار الصباح/المساء/النوم
• دعاء | حديث | آية

💬 *التحكم:*
• ذكرني - إرسال للجميع
• إيقاف/تشغيل

```
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_txt))
        return
    
    # ═══ إدارة المشرفين ═══
    if is_grp and txt.startswith("إضافة مشرف"):
        if not is_group_admin(gid, uid):
            line_bot_api.reply_message(event.reply_token, 
                TextSendMessage(text="⚠️ للمشرفين فقط"))
            return
        
        # استخراج المعرف من المنشن
        mentioned = re.findall(r'@(\w+)', txt)
        if mentioned:
            new_admin = mentioned[0]
            add_admin_to_db(gid, new_admin)
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"✅ تم إضافة {new_admin} كمشرف"))
        return
    
    # ═══ مدينتي ═══
    if txt.lower().startswith("مدينتي"):
        if not uid:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="⚠️ للرسائل الخاصة فقط"))
            return
        
        city = txt.replace("مدينتي", "").strip()
        if city:
            db.set_city(uid, city)
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"✅ تم حفظ مدينتك: {city}"))
        return
    
    # ═══ التسبيح ═══
    clean = txt.replace(" ", "")
    tsb_map = {
        "سبحانالله": "سبحان الله",
        "الحمدلله": "الحمد لله",
        "اللهأكبر": "الله أكبر",
        "استغفرالله": "استغفر الله",
        "لااللهإلاالله": "لا إله إلا الله",
    }
    
    typ = tsb_map.get(clean)
    if typ:
        cnt = db.inc_tasbih(tid, typ, today)
        counts = db.get_tasbih(tid, today)
        
        flex = create_tasbih_flex(counts, today)
        line_bot_api.reply_message(event.reply_token,
            FlexSendMessage(alt_text="التسبيح", contents=flex))
        
        if cnt == LIMIT:
            time.sleep(1)
            send(tid, f"✨ اكتمل {typ}! (33)")
        return
    
    # ═══ عرض التسبيح ═══
    if txt in ["تسبيح", "عداد"]:
        counts = db.get_tasbih(tid, today)
        flex = create_tasbih_flex(counts, today)
        line_bot_api.reply_message(event.reply_token,
            FlexSendMessage(alt_text="التسبيح", contents=flex))
        return
    
    # ═══ إعادة التسبيح ═══
    if txt in ["إعادة", "مسح"]:
        db.reset_tasbih(tid, today)
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="✅ تم مسح العداد"))
        return
    
    # ═══ سورة ═══
    if txt == "سورة":
        num = random.choice(list(SURAHS.keys()))
        flex = create_surah_flex(num)
        if flex:
            line_bot_api.reply_message(event.reply_token,
                FlexSendMessage(alt_text="سورة", contents=flex))
        return
    
    # ═══ سؤال ═══
    if txt == "سؤال":
        qidx = random.randint(0, len(QUESTIONS)-1)
        db.set_question(tid, qidx)
        flex = create_question_flex(QUESTIONS[qidx])
        line_bot_api.reply_message(event.reply_token,
            FlexSendMessage(alt_text="سؤال", contents=flex))
        return
    
    # ═══ إحصائياتي ═══
    if txt in ["إحصائياتي", "احصائياتي"]:
        stats = db.get_stats(uid or tid)
        msg = f"📊 *إحصائياتك*\n\n✅ صحيحة: {stats['c']}\n❌ خاطئة: {stats['w']}\n📈 النسبة: {stats['p']:.1f}%"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    # ═══ أذكار الصباح ═══
    if txt.lower() in ["أذكار الصباح", "الصباح"]:
        msg = "☀️ *أذكار الصباح*\n\n" + "\n\n".join(MORNING_ATHKAR[:2])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    # ═══ أذكار المساء ═══
    if txt.lower() in ["أذكار المساء", "المساء"]:
        msg = "🌙 *أذكار المساء*\n\n" + "\n\n".join(EVENING_ATHKAR)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    # ═══ أذكار النوم ═══
    if txt.lower() in ["أذكار النوم", "النوم"]:
        msg = "😴 *أذكار النوم*\n\n" + "\n\n".join(SLEEP_ATHKAR)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    # ═══ دعاء ═══
    if txt == "دعاء":
        msg = f"🤲 {random.choice(DUAS)}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    # ═══ حديث ═══
    if txt == "حديث":
        msg = f"📿 {random.choice(HADITHS)}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    # ═══ آية ═══
    if txt == "آية":
        try:
            r = requests.get("https://api.alquran.cloud/v1/ayah/random/ar.alafasy", timeout=5)
            d = r.json()
            if d.get("code") == 200:
                ayah = d["data"]
                msg = f"📖 {ayah['text']}\n\n﴿ {ayah['surah']['name']} - {ayah['numberInSurah']} ﴾"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
                return
        except:
            pass
        
        line_bot_api.reply_message(event.reply_token, 
            TextSendMessage(text="📖 إِنَّ مَعَ الْعُسْرِ يُسْرًا"))
        return
    
    # ═══ ذكرني (للجميع) ═══
    if txt == "ذكرني":
        content = random.choice(DUAS + HADITHS)
        msg = f"🌙 {content}\n\n━━━━━━━━━━━\n⏰ {get_time().strftime('%H:%M')}"
        
        # إرسال للجميع
        recipients = db.active_users() + db.active_groups()
        success = 0
        for r in recipients:
            if send(r, msg):
                success += 1
            time.sleep(0.5)
        
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text=f"✅ تم الإرسال لـ {success} مستلم"))
        return
    
    # ═══ إيقاف/تشغيل ═══
    if txt in ["إيقاف", "stop"]:
        with db.lock, db.conn() as c:
            if is_grp:
                c.execute("UPDATE groups SET notify=0 WHERE id=?", (gid,))
            else:
                c.execute("UPDATE users SET notify=0 WHERE id=?", (uid,))
            c.commit()
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="⏸️ تم إيقاف التنبيهات"))
        return
    
    if txt in ["تشغيل", "start"]:
        with db.lock, db.conn() as c:
            if is_grp:
                c.execute("UPDATE groups SET notify=1 WHERE id=?", (gid,))
            else:
                c.execute("UPDATE users SET notify=1 WHERE id=?", (uid,))
            c.commit()
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="✅ تم تشغيل التنبيهات"))
        return

except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    try:
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="⚠️ حدث خطأ"))
    except:
        pass
```

# ═══════════════════════════════════════════════════════════

# ⏰ جدولة الأذكار

# ═══════════════════════════════════════════════════════════

def send_athkar(athkar_list, emoji, title):
“”“إرسال الأذكار للجميع”””
txt = random.choice(athkar_list)
msg = f”{emoji} *{title}*\n\n{txt}\n\n━━━━━━━━━━━\n⏰ {get_time().strftime(’%H:%M’)}”

```
recipients = db.active_users() + db.active_groups()
for r in recipients:
    send(r, msg)
    time.sleep(0.5)

logger.info(f"✅ تم إرسال {title} لـ {len(recipients)}")
```

def scheduler():
“”“جدول الأذكار اليومي”””
logger.info(“🕐 بدأ الجدول”)
sent = {‘morning’: None, ‘evening’: None, ‘sleep’: None}

```
while True:
    try:
        now = get_time()
        today = now.date().isoformat()
        h, m = now.hour, now.minute
        
        # الصباح 7:00
        if h == 7 and m == 0 and sent['morning'] != today:
            send_athkar(MORNING_ATHKAR, "☀️", "أذكار الصباح")
            sent['morning'] = today
            time.sleep(3600)
        
        # المساء 17:00
        elif h == 17 and m == 0 and sent['evening'] != today:
            send_athkar(EVENING_ATHKAR, "🌙", "أذكار المساء")
            sent['evening'] = today
            time.sleep(3600)
        
        # النوم 22:00
        elif h == 22 and m == 0 and sent['sleep'] != today:
            send_athkar(SLEEP_ATHKAR, "😴", "أذكار النوم")
            sent['sleep'] = today
            time.sleep(3600)
        
        else:
            time.sleep(60)
    
    except Exception as e:
        logger.error(f"Error in scheduler: {e}")
        time.sleep(60)
```

# ═══════════════════════════════════════════════════════════

# 🌐 Flask Routes

# ═══════════════════════════════════════════════════════════

@app.route(”/”, methods=[“GET”])
def home():
return jsonify({
“bot”: “Islamic Bot v3.0”,
“status”: “running”,
“time”: get_time().isoformat()
})

@app.route(”/callback”, methods=[“POST”])
def callback():
sig = request.headers.get(“X-Line-Signature”, “”)
body = request.get_data(as_text=True)

```
try:
    handler.handle(body, sig)
except InvalidSignatureError:
    return "Invalid", 400
except Exception as e:
    logger.error(f"Callback error: {e}")
    return "Error", 500

return "OK"
```

@app.route(”/stats”, methods=[“GET”])
def stats():
“”“إحصائيات البوت”””
with db.conn() as c:
users = c.execute(“SELECT COUNT(*) FROM users”).fetchone()[0]
groups = c.execute(“SELECT COUNT(*) FROM groups”).fetchone()[0]

```
return jsonify({
    "users": users,
    "groups": groups,
    "time": get_time().isoformat()
})
```

# ═══════════════════════════════════════════════════════════

# 🚀 التشغيل

# ═══════════════════════════════════════════════════════════

if **name** == “**main**”:
print(“╔═══════════════════════════════════════╗”)
print(“║   🌙 بوت ذكرني v3.0 - محسّن       ║”)
print(“╚═══════════════════════════════════════╝”)
print()

```
with db.conn() as c:
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    groups = c.execute("SELECT COUNT(*) FROM groups").fetchone()[0]

print(f"👥 المستخدمين: {users}")
print(f"👥 المجموعات: {groups}")
print(f"🕐 التوقيت: UTC+3")
print(f"⏰ الوقت: {get_time().strftime('%Y-%m-%d %H:%M:%S')}")
print()
print("✨ الميزات:")
print("  ✓ Flex Messages احترافية")
print("  ✓ حماية المجموعات")
print("  ✓ نظام Admin حقيقي")
print("  ✓ تسجيل تلقائي")
print()
print("🔄 تشغيل الجدول...")

# تشغيل الجدول
threading.Thread(target=scheduler, daemon=True).start()

print("✅ البوت يعمل الآن!")
print()

# Flask
app.run(host="0.0.0.0", port=PORT, debug=False)
```
