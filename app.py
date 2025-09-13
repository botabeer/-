import os
import random
from flask import Flask, request, abort
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# تحميل القيم من .env
load_dotenv()
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# قائمة الأذكار والأدعية
adhkar_sabah = [
    "أذكار الصباح: أصبحنا وأصبح الملك لله...",
    "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور",
    "اللهم ما أصبح بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك..."
]
adhkar_masaa = [
    "أذكار المساء: أمسينا وأمسى الملك لله...",
    "اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير",
    "اللهم ما أمسى بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك..."
]
adhkar_nawm = [
    "أذكار النوم: باسمك ربي وضعت جنبي وبك أرفعه...",
    "اللهم قني عذابك يوم تبعث عبادك",
    "سبحان الله ٣٣ الحمد لله ٣٣ الله أكبر ٣٤"
]
ad3iya = [
    "اللهم إني أسألك العفو والعافية",
    "ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
    "اللهم اغفر لي ولوالدي ولجميع المسلمين"
]
ahadith = [
    "قال رسول الله ﷺ: لا تحقرن من المعروف شيئاً",
    "قال رسول الله ﷺ: الدين النصيحة",
    "قال رسول الله ﷺ: من سلك طريقاً يلتمس فيه علماً سهّل الله له به طريقاً إلى الجنة"
]
ayat = [
    "قال تعالى: واذكر ربك كثيراً وسبح بالعشي والإبكار",
    "قال تعالى: ألا بذكر الله تطمئن القلوب",
    "قال تعالى: فاذكروني أذكركم واشكروا لي ولا تكفرون"
]

# عداد التسبيح
tasbih_counter = {}

# جدولة الإرسال التلقائي
scheduler = BackgroundScheduler()

def send_auto_messages():
    users = list(tasbih_counter.keys())
    if not users:
        return
    chosen = random.sample(ad3iya + adhkar_sabah + adhkar_masaa + adhkar_nawm + ahadith + ayat, 3)
    message = "\n\n".join(chosen)
    for uid in users:
        line_bot_api.push_message(uid, TextSendMessage(text=message))

scheduler.add_job(send_auto_messages, "interval", hours=5)
scheduler.start()

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
    uid = event.source.user_id

    if uid not in tasbih_counter:
        tasbih_counter[uid] = 0

    if text == "صباح":
        reply = "\n\n".join(adhkar_sabah)
    elif text == "مساء":
        reply = "\n\n".join(adhkar_masaa)
    elif text == "نوم":
        reply = "\n\n".join(adhkar_nawm)
    elif text == "دعاء":
        reply = "\n\n".join(ad3iya)
    elif text == "حديث":
        reply = "\n\n".join(ahadith)
    elif text == "آية":
        reply = "\n\n".join(ayat)
    elif text == "تسبيح":
        tasbih_counter[uid] += 1
        reply = f"عدد التسبيح الحالي: {tasbih_counter[uid]}"
    elif text == "مساعدة":
        reply = (
            "الاوامر:\n"
            "صباح - عرض أذكار الصباح\n"
            "مساء - عرض أذكار المساء\n"
            "نوم - عرض أذكار النوم\n"
            "دعاء - عرض الأدعية\n"
            "حديث - عرض الأحاديث\n"
            "آية - عرض الآيات\n"
            "تسبيح - زيادة العداد\n"
            "تشغيل - تفعيل الارسال التلقائي\n"
            "إيقاف - إيقاف الارسال التلقائي"
        )
    elif text == "تشغيل":
        tasbih_counter[uid] = 0
        reply = "تم تفعيل الإرسال التلقائي لك."
    elif text == "إيقاف":
        if uid in tasbih_counter:
            del tasbih_counter[uid]
        reply = "تم إيقاف الإرسال التلقائي."
    else:
        reply = (
            "مرحبا بك\n\n"
            "بوت ذكرني، الذي يهدف إلى تذكيرك بالأذكار والأدعية والأحاديث النبوية الصحيحة.\n\n"
            "اكتب كلمة مساعدة لعرض الأوامر."
        )

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
