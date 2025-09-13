import os
import random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# تحميل القيم من ملف .env
load_dotenv()
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- محتوى مختصر للأذكار والأدعية والأحاديث ---
adhkar_sabah = ["أذكار الصباح: أصبحنا وأصبح الملك لله..."]
adhkar_masaa = ["أذكار المساء: أمسينا وأمسى الملك لله..."]
adhkar_nawm = ["أذكار النوم: باسمك ربي وضعت جنبي..."]
ad3yah = [
    "اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
    "اللهم إنك عفو تحب العفو فاعفُ عني"
]
ahadith = [
    "قال ﷺ: من قال سبحان الله وبحمده مائة مرة غفرت خطاياه وإن كانت مثل زبد البحر",
    "قال ﷺ: الكلمة الطيبة صدقة"
]

auto_short = [
    "سبحان الله وبحمده",
    "لا إله إلا الله وحده لا شريك له",
    "اللهم اغفر لي ولوالدي",
    "قال ﷺ: تبسمك في وجه أخيك صدقة",
    "الحمد لله الذي أحيانا بعدما أماتنا وإليه النشور"
]

# --- رسالة الترحيب ---
welcome_text = """مرحبا بك

بوت ذكرني، الذي يهدف إلى تذكيرك بالأذكار والأدعية والأحاديث النبوية الصحيحة.

ما الذي يقدمه لك البوت؟
1- أذكار الصباح
2- أذكار المساء
3- أذكار النوم
4- أدعية متنوعة
5- أحاديث نبوية صحيحة
6- آيات قرآنية قصيرة

طريقة الاستخدام:
- لعرض أذكار الصباح: اكتب (صباح)
- لعرض أذكار المساء: اكتب (مساء)
- لعرض أذكار النوم: اكتب (نوم)
- لعرض الأدعية: اكتب (دعاء)
- لعرض الأحاديث: اكتب (حديث)
- لعرض قائمة الأوامر: اكتب (مساعدة)

التحكم في الإرسال التلقائي:
- لتشغيل الإرسال التلقائي: اكتب (تشغيل)
- لإيقاف الإرسال التلقائي: اكتب (إيقاف)

المصادر:
- حصن المسلم
- كتب الأذكار الصحيحة
- القرآن الكريم

صانع البوت: عبير الدوسري
لا تنسوني من صالح دعائكم"""

# --- استقبال الأحداث ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    reply = None

    if text == "صباح":
        reply = "\n".join(adhkar_sabah)
    elif text == "مساء":
        reply = "\n".join(adhkar_masaa)
    elif text == "نوم":
        reply = "\n".join(adhkar_nawm)
    elif text == "دعاء":
        reply = random.choice(ad3yah)
    elif text == "حديث":
        reply = random.choice(ahadith)
    elif text == "مساعدة":
        reply = welcome_text
    elif text == "تشغيل":
        reply = "تم تشغيل الإرسال التلقائي"
    elif text == "إيقاف":
        reply = "تم إيقاف الإرسال التلقائي"
    else:
        reply = "مرحباً! اكتب (مساعدة) لعرض الأوامر."

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

# --- إرسال تلقائي ---
def send_auto_messages():
    msg = random.choice(auto_short)
    try:
        line_bot_api.broadcast(TextSendMessage(text=msg))
    except Exception as e:
        print("خطأ في الإرسال التلقائي:", e)

# --- جدولة الإرسال التلقائي ---
scheduler = BackgroundScheduler()
scheduler.add_job(send_auto_messages, 'cron', hour=5)
scheduler.add_job(send_auto_messages, 'cron', hour=10)
scheduler.add_job(send_auto_messages, 'cron', hour=14)
scheduler.add_job(send_auto_messages, 'cron', hour=18)
scheduler.add_job(send_auto_messages, 'cron', hour=22)
scheduler.start()

# --- نقطة البداية ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
