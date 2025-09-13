from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

active = True
tasbih_count = {}

adhkar = {
    "اذكار الصباح": "أصبحنا وأصبح الملك لله...",
    "اذكار المساء": "أمسينا وأمسى الملك لله...",
    "دعاء بعد الصلاة": "اللهم أعني على ذكرك وشكرك وحسن عبادتك 🤲",
    "دعاء النوم": "باسمك اللهم أموت وأحيا 🌙",
    "دعاء الاستيقاظ": "الحمد لله الذي أحيانا بعدما أماتنا وإليه النشور 🌞",
    "دعاء الجمعة": "اللهم اجعلنا من أهل الجمعة، واغفر لنا فيها ما مضى وما بقى 🕌",
    "دعاء السفر": "سبحان الذي سخر لنا هذا وما كنا له مقرنين ✈️",
    "دعاء دخول المسجد": "اللهم افتح لي أبواب رحمتك 🕌",
    "دعاء الخروج من المنزل": "بسم الله توكلت على الله ولا حول ولا قوة إلا بالله 🚪",
    "سورة الفاتحة": "بسم الله الرحمن الرحيم... (الفاتحة)",
    "سورة الكهف": "الحمد لله الذي أنزل على عبده الكتاب... (الآيات الأولى من الكهف)",
    "سورة الملك": "تبارك الذي بيده الملك... (الآيات الأولى من الملك)"
}

ayat = [
    "وَقُل رَّبِّ زِدْنِي عِلْمًا",
    "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
    "فاذكروني أذكركم"
]

ahadith = [
    "قال النبي ﷺ: بلغوا عني ولو آية",
    "قال النبي ﷺ: خيركم من تعلم القرآن وعلمه",
    "قال النبي ﷺ: لا تحقرن من المعروف شيئًا"
]

hikmah = [
    "من جد وجد ومن زرع حصد",
    "العلم نور يهدي إلى الحق",
    "النية الصالحة تحول العادة إلى عبادة"
]

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
    global active, tasbih_count
    text = event.message.text.strip()
    user_id = event.source.user_id if hasattr(event.source, "user_id") else None

    if text == "ايقاف":
        active = False
        reply = "🚫 تم إيقاف استقبال الرسائل."
    elif text in ["تشغيل", "تفعيل"]:
        active = True
        reply = "✅ تم تشغيل استقبال الرسائل."
    elif text == "مساعدة":
        reply = "📌 الأوامر: اذكار الصباح - اذكار المساء - دعاء بعد الصلاة - دعاء النوم - دعاء الاستيقاظ - دعاء الجمعة - دعاء السفر - دعاء دخول المسجد - دعاء الخروج من المنزل - سورة الفاتحة - سورة الكهف - سورة الملك - آية اليوم - حديث اليوم - حكمة اليوم - سبحان الله - الحمد لله - الله أكبر - ايقاف - تشغيل"
    else:
        if not active:
            return

        if text == "آية اليوم":
            reply = random.choice(ayat)
        elif text == "حديث اليوم":
            reply = random.choice(ahadith)
        elif text == "حكمة اليوم":
            reply = random.choice(hikmah)
        elif text in ["سبحان الله", "الحمد لله", "الله أكبر"]:
            if user_id not in tasbih_count:
                tasbih_count[user_id] = 0
            tasbih_count[user_id] += 1
            reply = f"{text} ({tasbih_count[user_id]})"
        elif text in adhkar:
            reply = adhkar[text]
        else:
            reply = "❓ لم أفهم الأمر. اكتب (مساعدة) لعرض الأوامر."

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run(port=5000)
