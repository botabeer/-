from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import random
import threading
import time

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

auto_reminder = True

WELCOME_MESSAGE = """مرحباً بك 👋
أنا بوت "ذكرني" لمساعدتك على الأذكار والأدعية والآيات والأحاديث.
اكتب "مساعدة" لرؤية جميع الأوامر المتاحة.
"""

HELP_MESSAGE = """الأوامر المتاحة:
صباح  → أذكار الصباح
مساء  → أذكار المساء
نوم   → أذكار النوم
دعاء  → أدعية عامة
حديث  → حديث نبوي
آية   → آية قرآنية
تسبيح → عداد التسبيح
تشغيل → تفعيل التذكير التلقائي
إيقاف → إيقاف التذكير التلقائي
"""

AZKAR_SABAH = """أذكار الصباح
آية الكرسي
المعوذات
اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور
"""

AZKAR_MASAA = """أذكار المساء
آية الكرسي
المعوذات
اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير
"""

AZKAR_NOUM = """أذكار النوم
باسمك ربي وضعت جنبي وبك أرفعه
اللهم قني عذابك يوم تبعث عبادك
"""

DUA_LIST = [
    "اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
    "رب اغفر لي ولوالدي وللمؤمنين يوم يقوم الحساب",
    "اللهم اجعلني لك شكارا لك ذكارا لك رهابا لك مطواعا لك مخبتا"
]

HADITH_LIST = [
    "قال رسول الله ﷺ: من قال سبحان الله وبحمده مئة مرة غفرت خطاياه وإن كانت مثل زبد البحر",
    "قال رسول الله ﷺ: الكلمة الطيبة صدقة",
    "قال رسول الله ﷺ: أحب الأعمال إلى الله أدومها وإن قل"
]

AYAT_LIST = [
    "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ ... [البقرة:255]",
    "قُلْ هُوَ اللَّهُ أَحَدٌ * اللَّهُ الصَّمَدُ ... [الإخلاص]",
    "قُلْ أَعُوذُ بِرَبِّ الْفَلَقِ ... [الفلق]"
]

tasbeeh_counter = {}

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
    global auto_reminder

    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "مساعدة":
        reply = HELP_MESSAGE
    elif text == "صباح":
        reply = AZKAR_SABAH
    elif text == "مساء":
        reply = AZKAR_MASAA
    elif text == "نوم":
        reply = AZKAR_NOUM
    elif text == "دعاء":
        reply = random.choice(DUA_LIST)
    elif text == "حديث":
        reply = random.choice(HADITH_LIST)
    elif text == "آية":
        reply = random.choice(AYAT_LIST)
    elif text == "تسبيح":
        tasbeeh_counter[user_id] = 0
        reply = "عداد التسبيح\nاكتب: سبحان الله - الحمد لله - الله أكبر"
    elif text in ["سبحان الله", "الحمد لله", "الله أكبر"]:
        if user_id in tasbeeh_counter:
            tasbeeh_counter[user_id] += 1
            reply = f"تم التسبيح {tasbeeh_counter[user_id]} مرة"
        else:
            reply = "اكتب تسبيح لتشغيل العداد"
    elif text == "تشغيل":
        auto_reminder = True
        reply = "تم تفعيل التذكير التلقائي"
    elif text == "إيقاف":
        auto_reminder = False
        reply = "تم إيقاف التذكير التلقائي"
    else:
        reply = WELCOME_MESSAGE

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

def send_reminders():
    while True:
        if auto_reminder:
            try:
                line_bot_api.broadcast(TextSendMessage(text=AZKAR_SABAH))
                time.sleep(5)
                line_bot_api.broadcast(TextSendMessage(text=AZKAR_MASAA))
                time.sleep(5)
                random_choice = random.choice(DUA_LIST + HADITH_LIST)
                line_bot_api.broadcast(TextSendMessage(text=random_choice))
                time.sleep(5)
                line_bot_api.broadcast(TextSendMessage(text=AZKAR_NOUM))
            except Exception as e:
                print("خطأ في التذكير:", e)
        time.sleep(60 * 60 * 6)

threading.Thread(target=send_reminders, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
