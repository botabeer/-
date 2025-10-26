import os
import json
import random
import threading
import time
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
from dotenv import load_dotenv
import sqlite3
from contextlib import contextmanager

# ═════════════════════
# ⚙️ الإعدادات
# ═════════════════════
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))
TIMEZONE = timezone(timedelta(hours=3))
get_time = lambda: datetime.now(TIMEZONE)

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("تأكد من إضافة مفاتيح LINE في .env")

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ═════════════════════
# 🗄️ قاعدة البيانات
# ═════════════════════
class DB:
    def __init__(self, path="bot.db"):
        self.path = path
        self.lock = threading.Lock()
        self._init()

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
            c.commit()

    def add_user(self, uid):
        with self.lock, self.conn() as c:
            c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
            c.commit()

    def add_group(self, gid):
        with self.lock, self.conn() as c:
            c.execute("INSERT OR IGNORE INTO groups (id) VALUES (?)", (gid,))
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

db = DB()

# ═════════════════════
# 📚 محتوى البوت
# ═════════════════════
TASBIH = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله", "لا إله إلا الله"]
ATHKAR = {
    "morning": ["أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ", "اللَّهُمَّ بِكَ أَصْبَحْنَا"],
    "evening": ["أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ", "اللَّهُمَّ بِكَ أَمْسَيْنَا"],
    "sleep": ["بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا"]
}
QUESTIONS = [
    {"q": "كم عدد أركان الإسلام؟", "opts": ["4", "5", "6"], "ans": 1},
    {"q": "ما أطول سورة في القرآن؟", "opts": ["آل عمران", "البقرة", "النساء"], "ans": 1}
]

BAD_WORDS = ["كلمة1", "كلمة2"]

# ═════════════════════
# 📨 استقبال Webhook
# ═════════════════════
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK'

# ═════════════════════
# 🗨️ معالجة الرسائل
# ═════════════════════
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()
    db.add_user(user_id)

    # 🚫 فحص الكلمات الممنوعة
    if any(word in msg for word in BAD_WORDS):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ لا يسمح بهذه الكلمات.")
        )
        return

    # 📿 أوامر التسبيح
    if msg.startswith("تسبيح"):
        typ = "تسبيح"
        cnt = db.inc_tasbih(user_id, typ, str(get_time().date()))
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{TASBIH[0]} ✅ العدد الحالي: {cnt}")
        )
        return

    # 🌄 أذكار الصباح والمساء
    if msg.lower() in ["اذكار الصباح", "اذكار المساء", "اذكار النوم"]:
        key = "morning" if "الصباح" in msg else "evening" if "المساء" in msg else "sleep"
        athkar_text = "\n".join(ATHKAR[key])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=athkar_text)
        )
        return

    # ❓ أسئلة شخصية
    if msg.lower() == "سؤال":
        q = random.choice(QUESTIONS)
        opts = "\n".join([f"{i+1}. {o}" for i,o in enumerate(q["opts"])])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{q['q']}\n{opts}")
        )
        return

    # 📊 إحصائيات التسبيح
    if msg.lower() == "تسبيح":
        data = db.inc_tasbih(user_id, "تسبيح", str(get_time().date()))
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"عدد مرات التسبيح اليوم: {data}")
        )
        return

    # ❌ أي رسالة غير معروفة
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="❌ الأمر غير معروف، جرب: تسبيح، اذكار الصباح، سؤال")
    )

# ═════════════════════
# 🚀 تشغيل التطبيق
# ═════════════════════
if __name__ == "__main__":
    print(f"Bot running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
