from flask import Flask, request, abort
from dotenv import load_dotenv
import os
import random
from apscheduler.schedulers.background import BackgroundScheduler
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# تحميل متغيرات البيئة من .env
load_dotenv()
app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# مشتركين للتذكير التلقائي (عند الضغط تشغيل يضاف user_id، وإيقاف يزيل)
subscribers = set()

# حالة تشغيل التذكير التلقائي بشكل عام
auto_reminder_enabled = True

# عداد التسبيح لكل مستخدم لكل عبارة
tasbih_limits = 30
tasbih_counts = {}  # structure: { user_id: {"سبحان الله": n, "الحمد لله": m, "الله أكبر": k} }

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# نصوص الأذكار والأدعية والآيات والأحاديث (مكتوبة كاملة)
FATIHA = """سورة الفاتحة
بسم الله الرحمن الرحيم
الحمد لله رب العالمين
الرحمن الرحيم
مالك يوم الدين
إياك نعبد وإياك نستعين
اهدنا الصراط المستقيم
صراط الذين أنعمت عليهم غير المغضوب عليهم ولا الضالين
"""

AYAT_KURSI = """آية الكرسي (البقرة 255)
اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ
لَا تَأْخُذُهُ سِنَةٌ وَلَا نَوْمٌ
لَهُ مَا فِي السَّمَاوَاتِ وَمَا فِي الْأَرْضِ
مَنْ ذَا الَّذِي يَشْفَعُ عِنْدَهُ إِلَّا بِإِذْنِهِ
يَعْلَمُ مَا بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ
وَلَا يُحِيطُونَ بِشَيْءٍ مِنْ عِلْمِهِ إِلَّا بِمَا شَاءَ
وَسِعَ كُرْسِيُّهُ السَّمَاوَاتِ وَالْأَرْضَ
وَلَا يَئُودُهُ حِفْظُهُمَا وَهُوَ الْعَلِيُّ الْعَظِيمُ
"""

IKHLAS = """سورة الإخلاص
قُلْ هُوَ اللَّهُ أَحَدٌ
اللَّهُ الصَّمَدُ
لَمْ يَلِدْ وَلَمْ يُولَدْ
وَلَمْ يَكُن لَّهُ كُفُوًا أَحَدٌ
"""

FALAQ = """سورة الفلق
قُلْ أَعُوذُ بِرَبِّ الْفَلَقِ
مِن شَرِّ مَا خَلَقَ
وَمِن شَرِّ غَاسِقٍ إِذَا وَقَبَ
وَمِن شَرِّ النَّفَّاثَاتِ فِي الْعُقَدِ
وَمِن شَرِّ حَاسِدٍ إِذَا حَسَدَ
"""

NAS = """سورة الناس
قُلْ أَعُوذُ بِرَبِّ النَّاسِ
مَلِكِ النَّاسِ
إِلَٰهِ النَّاسِ
مِن شَرِّ الْوَسْوَاسِ الْخَنَّاسِ
الَّذِي يُوَسْوِسُ فِي صُدُورِ النَّاسِ
مِنَ الْجِنَّةِ وَالنَّاسِ
"""

BAQARA_END = """آخر آيتين من سورة البقرة
آمَنَ الرَّسُولُ بِمَا أُنزِلَ إِلَيْهِ مِن رَبِّهِ وَالْمُؤْمِنُونَ
كُلٌّ آمَنَ بِاللَّهِ وَمَلَائِكَتِهِ وَكُتُبِهِ وَرُسُلِهِ لَا نُفَرِّقُ بَيْنَ أَحَدٍ مِّن رُّسُلِهِ
وَقَالُوا سَمِعْنَا وَأَطَعْنَا غُفْرَانَكَ رَبَّنَا وَإِلَيْكَ الْمَصِيرُ
لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا
لَهَا مَا كَسَبَتْ وَعَلَيْهَا مَا اكْتَسَبَتْ
رَبَّنَا لَا تُؤَاخِذْنَا إِن نَّسِينَا أَوْ أَخْطَأْنَا
رَبَّنَا وَلَا تَحْمِلْ عَلَيْنَا إِصْرًا كَمَا حَمَلْتَهُ عَلَى الَّذِينَ مِن قَبْلِنَا
رَبَّنَا وَلَا تُحَمِّلْنَا مَا لَا طَاقَةَ لَنَا بِهِ
وَاعْفُ عَنَّا وَاغْفِرْ لَنَا وَارْحَمْنَا
أَنتَ مَوْلَانَا فَانصُرْنَا عَلَى الْقَوْمِ الْكَافِرِينَ
"""

AZKAR_SABAH = FATIHA + "\n" + AYAT_KURSI + "\n" + IKHLAS + "\n" + FALAQ + "\n" + NAS + "\n" + """أذكار الصباح
أصبحنا وأصبح الملك لله والحمد لله، لا إله إلا الله وحده لا شريك له.
اللهم ما أصبح بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك فلك الحمد ولك الشكر.
اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور.
""" 

AZKAR_MASAA = FATIHA + "\n" + AYAT_KURSI + "\n" + IKHLAS + "\n" + FALAQ + "\n" + NAS + "\n" + """أذكار المساء
أمسينا وأمسى الملك لله والحمد لله، لا إله إلا الله وحده لا شريك له.
اللهم ما أمسى بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك فلك الحمد ولك الشكر.
اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير.
"""

AZKAR_NAWM = AYAT_KURSI + "\n" + BAQARA_END + "\n" + FATIHA + "\n" + IKHLAS + "\n" + FALAQ + "\n" + NAS + "\n" + """أذكار النوم
باسمك ربي وضعت جنبي وبك أرفعه، إن أمسكت نفسي فارحمها، وإن أرسلتها فاحفظها بما تحفظ به عبادك الصالحين.
اللهم قني عذابك يوم تبعث عبادك.
"""

DUA_LIST = [
"اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
"اللهم اغفر لي ولوالدي وللمؤمنين والمؤمنات",
"اللهم ارزقني رزقاً حلالاً طيباً واسعاً"
]

HADITH_LIST = [
"قال رسول الله صلى الله عليه وسلم: من قال سبحان الله وبحمده مئة مرة غفرت له ذنوبه وإن كانت مثل زبد البحر. رواه مسلم",
"قال رسول الله صلى الله عليه وسلم: الكلمة الطيبة صدقة. متفق عليه",
"قال رسول الله صلى الله عليه وسلم: أحب الأعمال إلى الله أدومها وإن قل"
]

# رسالة الترحيب ومساعدة (مختصرة وواضحة)
WELCOME = """مرحباً بك في بوت ذكرني
بوت إسلامي يذكرك بالأذكار والأدعية والآيات والأحاديث الصحيحة.
اكتب 'مساعدة' لعرض الأوامر المتاحة.
"""

HELP_TEXT = """الأوامر المتاحة
صباح  لعرض أذكار الصباح
مساء  لعرض أذكار المساء
نوم   لعرض أذكار النوم
آية   لعرض آية الكرسي
دعاء  لعرض أدعية
حديث  لعرض أحاديث
تسبيح لبدء عداد التسبيح (سبحان الله / الحمد لله / الله أكبر)
تشغيل لتفعيل التذكير التلقائي
إيقاف لتوقيف التذكير التلقائي
مساعدة لعرض هذه القائمة
"""

# إرسال الرسائل للمشتركين (خاص وقروبات)
def push_to_subscribers(text):
    for uid in list(subscribers):
        try:
            line_bot_api.push_message(uid, TextSendMessage(text=text))
        except Exception as e:
            # لو فشل الإرسال لأي مشترك نكمل مع الباقين
            print("خطأ إرسال لمشترك:", uid, e)

# جداول زمنية للتذكير التلقائي
scheduler = BackgroundScheduler()

# أذكار الصباح 4:00 فجراً
scheduler.add_job(lambda: push_to_subscribers(AZKAR_SABAH), 'cron', hour=4, minute=0)
# أذكار المساء 16:00
scheduler.add_job(lambda: push_to_subscribers(AZKAR_MASAA), 'cron', hour=16, minute=0)
# أذكار النوم 22:00
scheduler.add_job(lambda: push_to_subscribers(AZKAR_NAWM), 'cron', hour=22, minute=0)
# إعادة تصفير عداد التسبيح كل منتصف الليل
def reset_tasbih_counts():
    global tasbih_counts
    tasbih_counts = {}
scheduler.add_job(reset_tasbih_counts, 'cron', hour=0, minute=0)

scheduler.start()

# Webhook endpoint
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global auto_reminder_enabled
    user_id = event.source.user_id
    text = event.message.text.strip()

    # أوامر محددة فقط — يتجاهل أي نص آخر
    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return
    if text == "صباح":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_SABAH))
        return
    if text == "مساء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_MASAA))
        return
    if text == "نوم":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_NAWM))
        return
    if text == "آية":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AYAT_KURSI))
        return
    if text == "دعاء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(DUA_LIST)))
        return
    if text == "حديث":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(HADITH_LIST)))
        return
    if text == "تشغيل":
        subscribers.add(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تفعيل التذكير التلقائي"))
        return
    if text == "إيقاف":
        subscribers.discard(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف التذكير التلقائي"))
        return
    # تسبيح: بدء أو زيادة حسب العبارة
    if text == "تسبيح":
        ensure_user_counts(user_id)
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/30\nالحمد لله: {counts['الحمد لله']}/30\nالله أكبر: {counts['الله أكبر']}/30"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return
    if text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        ensure_user_counts(user_id)
        if tasbih_counts[user_id][text] < tasbih_limits:
            tasbih_counts[user_id][text] += 1
            if tasbih_counts[user_id][text] >= tasbih_limits:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {text} ({tasbih_limits} مرة)"))
            else:
                counts = tasbih_counts[user_id]
                status = f"سبحان الله: {counts['سبحان الله']}/30\nالحمد لله: {counts['الحمد لله']}/30\nالله أكبر: {counts['الله أكبر']}/30"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{text} مكتمل ({tasbih_limits} مرة)"))
        return

    # أي نص آخر نتجاهله (لا نرد)
    return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
