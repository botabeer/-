from flask import Flask, request, abort
from dotenv import load_dotenv
import os
from apscheduler.schedulers.background import BackgroundScheduler
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# تحميل متغيرات البيئة
load_dotenv()
app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# رسائل الأذكار والأدعية
اذكار_الصباح = """أذكار الصباح
آية الكرسي
المعوذات
اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور
"""

اذكار_المساء = """أذكار المساء
آية الكرسي
المعوذات
اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير
"""

اذكار_النوم = """أذكار النوم
باسمك ربي وضعت جنبي وبك أرفعه
اللهم قني عذابك يوم تبعث عبادك
"""

اية_الكرسي = """آية الكرسي
اللّه لا إله إلا هو الحي القيوم لا تأخذه سنة ولا نوم...
"""

دعاء = """دعاء
اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار
"""

حديث = """حديث
قال رسول الله ﷺ: "الكلمة الطيبة صدقة"
"""

# عداد التسبيح
عداد = {}

# الترحيب + الأوامر
رسالة_الترحيب = """مرحباً بك في بوت ذكرني
البوت يرسل تذكير تلقائي بالأذكار والأدعية والآيات

الأوامر المتاحة
صباح : أذكار الصباح
مساء : أذكار المساء
نوم : أذكار النوم
آية : آية الكرسي
دعاء : دعاء
حديث : حديث نبوي
تسبيح : عداد للتسبيح
تشغيل : لتفعيل التذكير التلقائي
إيقاف : لإيقاف التذكير التلقائي
"""

# نشر تلقائي
المشتركين = set()

def ارسال_تلقائي():
    for user in المشتركين:
        line_bot_api.push_message(user, TextSendMessage(text=اذكار_الصباح))
        line_bot_api.push_message(user, TextSendMessage(text=اذكار_المساء))
        line_bot_api.push_message(user, TextSendMessage(text=اذكار_النوم))

scheduler = BackgroundScheduler()
scheduler.add_job(ارسال_تلقائي, "interval", hours=24)
scheduler.start()

# استقبال الرسائل
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
    user_id = event.source.user_id
    النص = event.message.text.strip()

    if النص == "صباح":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=اذكار_الصباح))
    elif النص == "مساء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=اذكار_المساء))
    elif النص == "نوم":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=اذكار_النوم))
    elif النص == "آية":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=اية_الكرسي))
    elif النص == "دعاء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=دعاء))
    elif النص == "حديث":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=حديث))
    elif النص == "تسبيح":
        عداد[user_id] = عداد.get(user_id, 0) + 1
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"عدد التسبيحات: {عداد[user_id]}"))
    elif النص == "تشغيل":
        المشتركين.add(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تفعيل التذكير التلقائي"))
    elif النص == "إيقاف":
        المشتركين.discard(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف التذكير التلقائي"))
    elif النص == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=رسالة_الترحيب))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب مساعدة لعرض الأوامر"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
