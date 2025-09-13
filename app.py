from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

scheduler = BackgroundScheduler()
scheduler.start()

# الأذكار والأدعية والآيات والأحاديث (نماذج مبسطة - يمكن التوسع)
azkar_sabah = """
أذكار الصباح
آية الكرسي
المعوذات
اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور
"""

azkar_masa = """
أذكار المساء
آية الكرسي
المعوذات
اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير
"""

azkar_nawm = """
أذكار النوم
باسمك ربي وضعت جنبي وبك أرفعه
اللهم قني عذابك يوم تبعث عبادك
"""

def send_sabah():
    line_bot_api.broadcast(TextSendMessage(text=azkar_sabah))

def send_masa():
    line_bot_api.broadcast(TextSendMessage(text=azkar_masa))

# جدولة الصباح والمساء
scheduler.add_job(send_sabah, 'cron', hour=6, minute=0)
scheduler.add_job(send_masa, 'cron', hour=18, minute=0)

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

    if text == "صباح":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=azkar_sabah))
    elif text == "مساء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=azkar_masa))
    elif text == "نوم":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=azkar_nawm))
    elif text == "تشغيل":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تشغيل التذكير التلقائي"))
    elif text == "إيقاف":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف التذكير التلقائي"))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب صباح - مساء - نوم - تشغيل - إيقاف"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
