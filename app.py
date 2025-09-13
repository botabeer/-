from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os

app = Flask(__name__)

# قراءة التوكن والسر من .env
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# المحتوى الكامل (اذكار + ادعية + آيات + احاديث)
full_text = """
أذكار الصباح
اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور
... (تكملة النصوص كاملة هنا)

أذكار المساء
اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير
...

أذكار النوم
باسمك ربي وضعت جنبي وبك أرفعه فإن أمسكت نفسي فارحمها وإن أرسلتها فاحفظها بما تحفظ به عبادك الصالحين
...

الأدعية
اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار
...

الآيات
سورة الفاتحة
بسم الله الرحمن الرحيم
الحمد لله رب العالمين
الرحمن الرحيم
مالك يوم الدين
إياك نعبد وإياك نستعين
اهدنا الصراط المستقيم
صراط الذين أنعمت عليهم غير المغضوب عليهم ولا الضالين

آية الكرسي
الله لا إله إلا هو الحي القيوم لا تأخذه سنة ولا نوم ...
...

الأحاديث
قال رسول الله صلى الله عليه وسلم: من قال سبحان الله وبحمده في يوم مائة مرة حطت خطاياه وإن كانت مثل زبد البحر
...

الأوامر
صباح
مساء
نوم
دعاء
حديث
آية
مساعدة
تشغيل
إيقاف
تسبيح
"""

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    if text in ["صباح", "مساء", "نوم", "دعاء", "حديث", "آية", "مساعدة", "تشغيل", "إيقاف", "تسبيح"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=full_text))

# جدولة الإرسال التلقائي
scheduler = BackgroundScheduler()

def send_auto():
    # إرسال النص الكامل تلقائياً (يمكن تخصيص جزء منه)
    try:
        line_bot_api.broadcast(TextSendMessage(text=full_text))
    except Exception as e:
        print("خطأ في الإرسال التلقائي:", e)

# أذكار الصباح 4 فجراً
scheduler.add_job(send_auto, "cron", hour=4, minute=0)
# أذكار المساء 4 عصراً
scheduler.add_job(send_auto, "cron", hour=16, minute=0)
# أذكار النوم 10 مساء
scheduler.add_job(send_auto, "cron", hour=22, minute=0)
# نشر عشوائي 5 مرات باليوم (مثال موزعة)
scheduler.add_job(send_auto, "cron", hour=8, minute=0)
scheduler.add_job(send_auto, "cron", hour=12, minute=0)
scheduler.add_job(send_auto, "cron", hour=15, minute=0)
scheduler.add_job(send_auto, "cron", hour=19, minute=0)
scheduler.add_job(send_auto, "cron", hour=23, minute=0)

scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
