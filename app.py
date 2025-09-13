from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
import os, random, atexit
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

from dotenv import load_dotenv
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

broadcast_active = False
tasbih_count = {}

# ---------------- الأذكار والأدعية ----------------
adhkar = {
    "اذكار الصباح": "☀️ أذكار الصباح:\nأصبحنا وأصبح الملك لله...",
    "اذكار المساء": "🌙 أذكار المساء:\nأمسينا وأمسى الملك لله...",
    "دعاء بعد الصلاة": "🕌 دعاء بعد الصلاة:\nأستغفر الله (3 مرات)...",
    "دعاء النوم": "🌙 دعاء النوم:\nباسمك ربي وضعت جنبي...",
    "دعاء الاستيقاظ": "🌅 دعاء الاستيقاظ:\nالحمد لله الذي أحيانا...",
    "دعاء الجمعة": "اللهم اجعلنا من المقبولين في يوم الجمعة...",
    "دعاء السفر": "اللهم إنا نسألك في سفرنا هذا البر والتقوى...",
    "دعاء دخول المسجد": "اللهم افتح لي أبواب رحمتك.",
    "دعاء الخروج من المسجد": "اللهم إني أسألك من فضلك.",
    "دعاء الخروج من المنزل": "بسم الله، توكلت على الله، ولا حول ولا قوة إلا بالله.",
    "دعاء الكرب": "لا إله إلا الله العظيم الحليم...",
    "دعاء الاستخارة": "اللهم إني استخيرك بعلمك...",
    "دعاء الرزق": "اللهم ارزقني رزقاً حلالاً طيباً..."
}

quran = {
    "سورة الفاتحة": "بسم الله الرحمن الرحيم...",
    "سورة الكهف": "الحمد لله الذي أنزل على عبده الكتاب...",
    "سورة الملك": "تبارك الذي بيده الملك...",
    "آية الكرسي": "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ...",
    "المعوذات": "قُلْ هُوَ اللَّهُ أَحَدٌ..."
}

ayat = ["وَقُل رَّبِّ زِدْنِي عِلْمًا", "إِنَّ مَعَ الْعُسْرِ يُسْرًا"]
ahadith = ["قال النبي ﷺ: خيركم من تعلم القرآن وعلمه", "قال النبي ﷺ: الكلمة الطيبة صدقة"]
hikmah = ["من جد وجد ومن زرع حصد", "العلم نور يهدي إلى الحق"]

# ---------------- النشر التلقائي ----------------
scheduler = BackgroundScheduler()

def send_morning_broadcast():
    if not broadcast_active:
        return
    text = adhkar["اذكار الصباح"] + "\n\n📖 آية اليوم:\n" + random.choice(ayat)
    try:
        line_bot_api.broadcast(TextSendMessage(text=text))
    except Exception as e:
        print("Error broadcasting morning:", e)

def send_evening_broadcast():
    if not broadcast_active:
        return
    text = adhkar["اذكار المساء"] + "\n\n📜 حديث اليوم:\n" + random.choice(ahadith)
    try:
        line_bot_api.broadcast(TextSendMessage(text=text))
    except Exception as e:
        print("Error broadcasting evening:", e)

scheduler.add_job(send_morning_broadcast, "cron", hour=7, minute=0)
scheduler.add_job(send_evening_broadcast, "cron", hour=19, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

WELCOME_TEXT = (
    "👋 أهلاً بك في بوت الأذكار والقرآن 📖\n\n"
    "🌟 الأوامر:\n"
    "- اذكار الصباح / اذكار المساء / دعاء النوم / دعاء الاستيقاظ / دعاء بعد الصلاة\n"
    "- دعاء الجمعة / دعاء السفر / دعاء دخول المسجد / دعاء الخروج من المسجد / دعاء الخروج من المنزل\n"
    "- دعاء الكرب / دعاء الاستخارة / دعاء الرزق\n"
    "- سورة الفاتحة / سورة الكهف / سورة الملك / آية الكرسي / المعوذات\n"
    "- آية اليوم / حديث اليوم / حكمة اليوم\n"
    "- التسبيح: سبحان الله / الحمد لله / الله أكبر\n"
    "- تشغيل / ايقاف / مساعدة"
)

@handler.add(FollowEvent)
def handle_follow(event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=WELCOME_TEXT))
    except Exception as e:
        print("FollowEvent error:", e)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global broadcast_active, tasbih_count
    text = event.message.text.strip()
    user_id = getattr(event.source, "user_id", None)

    if text == "ايقاف":
        broadcast_active = False
        reply = "🚫 تم إيقاف النشر التلقائي."
    elif text in ["تشغيل", "تفعيل"]:
        broadcast_active = True
        reply = "✅ تم تفعيل النشر التلقائي (أذكار الصباح 7:00، المساء 19:00)."
    elif text == "مساعدة":
        reply = WELCOME_TEXT
    elif text in adhkar:
        reply = adhkar[text]
    elif text in quran:
        reply = quran[text]
    elif text == "آية اليوم":
        reply = random.choice(ayat)
    elif text == "حديث اليوم":
        reply = random.choice(ahadith)
    elif text == "حكمة اليوم":
        reply = random.choice(hikmah)
    elif text in ["سبحان الله", "الحمد لله", "الله أكبر"]:
        if user_id:
            tasbih_count.setdefault(user_id, 0)
            tasbih_count[user_id] += 1
            reply = f"{text} ({tasbih_count[user_id]})"
        else:
            reply = text
    else:
        reply = "❓ لم أفهم الأمر. اكتب (مساعدة) لعرض الأوامر."

    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    except Exception as e:
        print("reply error:", e)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
