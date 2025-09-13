from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# قاعدة بيانات مؤقتة للمشتركين
subscribers = set()
tasbih_counter = {}

# نصوص للأذكار والأدعية
adhkar_sabah = """أذكار الصباح كاملة...
(النصوص الكاملة هنا)"""

adhkar_masaa = """أذكار المساء كاملة...
(النصوص الكاملة هنا)"""

adhkar_noom = """أذكار النوم كاملة (مع الفاتحة، آية الكرسي، الإخلاص، الفلق، الناس، آخر البقرة)...
(النصوص الكاملة هنا)"""

ad3ya = ["اللهم اغفر لي ولوالدي", "اللهم ارزقني علماً نافعاً", "اللهم اجعلني من أهل القرآن"]

ahadith = ["قال رسول الله ﷺ: من قال سبحان الله وبحمده مئة مرة حطت خطاياه.", 
"قال رسول الله ﷺ: لا تحقرن من المعروف شيئاً."]

ayat = ["إِنَّ مَعَ الْعُسْرِ يُسْرًا", "وَقُل رَّبِّ زِدْنِي عِلْمًا"]

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
    text = event.message.text.strip()

    if text == "مساعدة":
        reply = "الأوامر: صباح - مساء - نوم - دعاء - حديث - آية - تسبيح - تشغيل - إيقاف"
    elif text == "صباح":
        reply = adhkar_sabah
    elif text == "مساء":
        reply = adhkar_masaa
    elif text == "نوم":
        reply = adhkar_noom
    elif text == "دعاء":
        reply = random.choice(ad3ya)
    elif text == "حديث":
        reply = random.choice(ahadith)
    elif text == "آية":
        reply = random.choice(ayat)
    elif text == "تشغيل":
        subscribers.add(user_id)
        reply = "تم تفعيل الإرسال التلقائي بنجاح. سيتم تذكيرك يومياً."
    elif text == "إيقاف":
        subscribers.discard(user_id)
        reply = "تم إيقاف الإرسال التلقائي. لن تستقبل التنبيهات إلا إذا أعدت تشغيل البوت."
    elif text.startswith("تسبيح"):
        count = tasbih_counter.get(user_id, 0) + 1
        tasbih_counter[user_id] = count
        reply = f"عدد التسبيح الحالي: {count}"
    else:
        reply = "بوت ذكرني: صباح - مساء - نوم - دعاء - حديث - آية - تسبيح - تشغيل - إيقاف"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

# وظيفة الإرسال التلقائي
def send_auto():
    if not subscribers: return
    items = [random.choice([adhkar_sabah, adhkar_masaa, adhkar_noom, random.choice(ad3ya), random.choice(ahadith), random.choice(ayat)]) for _ in range(3)]
    text = "\n\n".join(items)
    for uid in subscribers:
        line_bot_api.push_message(uid, TextSendMessage(text=text))

scheduler = BackgroundScheduler()
scheduler.add_job(send_auto, 'interval', hours=4)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
