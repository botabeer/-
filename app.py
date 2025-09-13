from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, threading, time

app = Flask(__name__)

# جلب التوكن والسر من .env
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# قوائم الأذكار والأدعية والآيات
adhkar_sabah = [
    "أذكار الصباح كاملة:

أصبحنا وأصبح الملك لله... (النص كامل)",
    "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور.",
    "سيد الاستغفار: اللهم أنت ربي لا إله إلا أنت..."
]

adhkar_masa = [
    "أذكار المساء كاملة:

أمسينا وأمسى الملك لله... (النص كامل)",
    "اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير.",
    "رضيت بالله رباً، وبالإسلام ديناً، وبمحمد صلى الله عليه وسلم نبياً."
]

adhkar_nawm = [
    "أذكار النوم:

باسمك ربي وضعت جنبي وبك أرفعه...",
    "اللهم قني عذابك يوم تبعث عبادك.",
    "آية الكرسي:
الله لا إله إلا هو الحي القيوم... (النص كامل)",
    "آخر آيتين من سورة البقرة:
آمن الرسول بما أنزل إليه من ربه... (النص كامل)",
    "سورة الإخلاص، الفلق، الناس."
]

ad3iya = [
    "اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار.",
    "رب اغفر لي ولوالدي وللمؤمنين يوم يقوم الحساب.",
    "اللهم إني أعوذ بك من الهم والحزن وأعوذ بك من العجز والكسل."
]

ahadith = [
    "قال رسول الله صلى الله عليه وسلم: (من قال سبحان الله وبحمده في يوم مئة مرة حطت خطاياه وإن كانت مثل زبد البحر).",
    "قال رسول الله صلى الله عليه وسلم: (الكلمة الطيبة صدقة).",
    "قال رسول الله صلى الله عليه وسلم: (من لا يشكر الناس لا يشكر الله)."
]

ayat = [
    "الفاتحة:
بسم الله الرحمن الرحيم الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدين إياك نعبد وإياك نستعين اهدنا الصراط المستقيم صراط الذين أنعمت عليهم غير المغضوب عليهم ولا الضالين",
    "آية الكرسي:
الله لا إله إلا هو الحي القيوم لا تأخذه سنة ولا نوم...",
    "سورة الفلق:
قل أعوذ برب الفلق من شر ما خلق ومن شر غاسق إذا وقب ومن شر النفاثات في العقد ومن شر حاسد إذا حسد",
    "سورة الناس:
قل أعوذ برب الناس ملك الناس إله الناس من شر الوسواس الخناس الذي يوسوس في صدور الناس من الجنة والناس"
]

# عداد التسبيح
tasbih_count = {}

# رسالة ترحيب مختصرة
welcome_message = """
بوت ذكرني، يهدف إلى تذكيرك بالأذكار والأدعية والأحاديث الصحيحة.
للتحكم في التلقائي اكتب (تشغيل) أو (إيقاف).
للاستخدام اكتب: صباح - مساء - نوم - دعاء - حديث - آية - تسبيح - مساعدة
"""

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
        reply = welcome_message
    elif text == "صباح":
        reply = "\n\n".join(adhkar_sabah)
    elif text == "مساء":
        reply = "\n\n".join(adhkar_masa)
    elif text == "نوم":
        reply = "\n\n".join(adhkar_nawm)
    elif text == "دعاء":
        reply = "\n\n".join(ad3iya)
    elif text == "حديث":
        reply = "\n\n".join(ahadith)
    elif text == "آية":
        reply = "\n\n".join(ayat)
    elif text == "تسبيح":
        count = tasbih_count.get(user_id, 0) + 1
        tasbih_count[user_id] = count
        reply = f"عدد التسبيحات: {count}"
    elif text == "تشغيل":
        reply = "تم تشغيل الإرسال التلقائي."
    elif text == "إيقاف":
        reply = "تم إيقاف الإرسال التلقائي. لن تستقبل التنبيهات إلا إذا أعدت التشغيل."
    else:
        reply = "اكتب (مساعدة) لعرض الأوامر."

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
