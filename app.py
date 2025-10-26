import os
import json
import random
import threading
import time
import re
import logging
from collections import defaultdict
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# === إعداد البوت ===
load_dotenv()
TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not TOKEN or not SECRET:
    raise ValueError("يرجى ضبط مفاتيح LINE في ملف .env")

app = Flask(__name__)
line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# === تحميل محتوى الذكر والدعاء والقرآن ===
try:
    with open("content.json", encoding="utf-8") as f:
        CONTENT = json.load(f)
except Exception as e:
    logging.error(f"خطأ في قراءة ملف content.json: {e}")
    CONTENT = {"athkar": [], "duas": [], "hadiths": [], "quran": []}

# === إعدادات البوت ===
SPAM_LIMIT = 5
LINK_LIMIT = 2
TASBIH_LIMIT = 33
REMINDER_INTERVAL = 3600  # بالثواني

spam = defaultdict(list)
links = defaultdict(lambda: defaultdict(int))
tasbih_counts = defaultdict(lambda: defaultdict(int))
subscribed_groups = set()
lock = threading.Lock()

# === حماية من السبام ===
def rate_limit(uid, gid, limit=SPAM_LIMIT, period=10):
    now = time.time()
    key = f"{gid}:{uid}"
    with lock:
        spam[key] = [t for t in spam[key] if now - t < period]
        spam[key].append(now)
    return len(spam[key]) <= limit

def check_links(txt, gid):
    urls = re.findall(r'https?://[^\s]+', txt)
    if not urls:
        return True
    with lock:
        for url in urls:
            links[gid][url] += 1
            if links[gid][url] > LINK_LIMIT:
                return False
    return True

# === وظائف البوت ===
def handle_tasbih(txt, tid):
    athkar_list = CONTENT.get("athkar", [])
    if not athkar_list:
        return "لا يوجد أذكار حالياً."
    clean = txt.replace(" ", "").lower()
    tasbih_map = {s.replace(" ", "").lower(): s for s in athkar_list}
    if clean not in tasbih_map:
        return None
    typ = tasbih_map[clean]
    tasbih_counts[tid][typ] += 1
    count = tasbih_counts[tid][typ]
    if count >= TASBIH_LIMIT:
        return f"{typ} اكتمل ({count}/{TASBIH_LIMIT})"
    return f"{typ} العدد: {count}/{TASBIH_LIMIT}"

def random_reminder():
    category = random.choice(["athkar", "duas", "hadiths", "quran"])
    data = CONTENT.get(category, [])
    if not data:
        return "لا يوجد محتوى متاح حالياً."
    return random.choice(data)

def help_message():
    return (
        "بوت ذكرني الإسلامي\n\n"
        "التسبيح:\n"
        "- سبحان الله\n- الحمد لله\n- الله أكبر\n- استغفر الله\n- لا إله إلا الله\n\n"
        "كل ذكر 33 مرة، اكتب إعادة لمسح العداد.\n\n"
        "اكتب ذكرني لإرسال ذكر أو حديث أو آية.\n"
    )

# === التذكير التلقائي للمجموعات ===
def auto_reminder():
    while True:
        if subscribed_groups:
            text = random_reminder()
            for gid in list(subscribed_groups):
                try:
                    line_bot_api.push_message(gid, TextSendMessage(text=text))
                    logging.info(f"تم إرسال تذكير إلى المجموعة {gid}")
                except Exception as e:
                    logging.error(f"فشل إرسال إلى {gid}: {e}")
        time.sleep(REMINDER_INTERVAL)

threading.Thread(target=auto_reminder, daemon=True).start()

# === التعامل مع الرسائل ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    txt = event.message.text.strip()
    uid = getattr(event.source, "user_id", None)
    gid = getattr(event.source, "group_id", None)
    tid = uid or gid

    # حماية من السبام والروابط
    if gid and uid:
        if not rate_limit(uid, gid):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="توقف عن إرسال الرسائل بسرعة."))
            return
        if not check_links(txt, gid):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم حظر الرابط المكرر."))
            return

    txt_lower = txt.lower()
    response = None

    if txt_lower in ["مساعدة", "الاوامر", "help", "؟"]:
        response = help_message()
    elif txt_lower in ["إعادة", "مسح", "إعادة التسبيح"]:
        tasbih_counts[tid] = defaultdict(int)
        response = "تم مسح العداد."
    elif txt_lower == "ذكرني":
        response = random_reminder()
    elif txt_lower == "تفعيل التذكير" and gid:
        subscribed_groups.add(gid)
        response = "تم تفعيل التذكير التلقائي للمجموعة."
    elif txt_lower == "إيقاف التذكير" and gid:
        subscribed_groups.discard(gid)
        response = "تم إيقاف التذكير التلقائي للمجموعة."
    else:
        response = handle_tasbih(txt, tid)

    if response:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response))

# === Webhook ===
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        logging.error(f"خطأ في webhook: {e}")
    return "OK"

# === صفحة رئيسية لتجنب 404 ===
@app.route("/")
def index():
    return "بوت ذكرني الإسلامي يعمل!"

# === تشغيل السيرفر ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logging.info(f"تشغيل السيرفر على المنفذ {port}")
    app.run(host="0.0.0.0", port=port)
