from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, SourceGroup, SourceUser
import os
import threading
import random
import time
import re

app = Flask(__name__)

# ---------------- إعداد البوت ---------------- #
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- بيانات التسبيح ---------------- #
tasbih_limits = 33
tasbih_counts = {}  # { user_id: {"سبحان الله": n, "الحمد لله": m, "الله أكبر": k} }

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# ---------------- حماية الروابط ---------------- #
links_count = {}  # عداد الروابط لكل مستخدم
def contains_link(text):
    url_pattern = r"(https?://\S+|www\.\S+)"
    return re.search(url_pattern, text)

# ---------------- الأدعية المحددة ---------------- #
specific_duas = {
    "دعاء السفر": "اللهم أنت الصاحب في السفر والخليفة في الأهل اللهم إني أعوذ بك من وعثاء السفر وكآبة المنظر وسوء المنقلب في المال والأهل",
    "دعاء الكرب": "لا إله إلا أنت سبحانك إني كنت من الظالمين اللهم فرج همي وكربي",
    "دعاء الاستخارة": "اللهم إني استخيرك بعلمك واستقدرك بقدرتك وأسألك من فضلك العظيم فإنك تقدر ولا أقدر وتعلم ولا أعلم وأنت علام الغيوب",
    "دعاء الصباح": "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك المصير",
    "دعاء المساء": "اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك النشور",
    "دعاء الفرج": "اللهم إني أعوذ بك من الهم والحزن والعجز والكسل والبخل والجبن وضلع الدين وغلبة الرجال",
    "دعاء القلق": "اللهم إني أعوذ بك من الهم والحزن وأعوذ بك من العجز والكسل وأعوذ بك من الجبن والبخل وأعوذ بك من غلبة الدين وقهر الرجال",
    "دعاء الشفاء": "اللهم رب الناس أذهب البأس واشف أنت الشافي لا شفاء إلا شفاؤك شفاء لا يغادر سقما",
    "دعاء الاستغفار": "أستغفر الله العظيم الذي لا إله إلا هو الحي القيوم وأتوب إليه",
    "دعاء الرزق": "اللهم ارزقني رزقا حلالا طيبا مباركا فيه واجعلني شاكرا لنعمك",
    "دعاء النجاح": "اللهم وفقني ونجحني وحقق لي ما أحب وأرضني بما قسمته لي",
    "دعاء البركة": "اللهم اجعل عملي كله خالصا لوجهك الكريم وبارك لي فيما أعطيتني"
}

# ---------------- الأذكار اليومية ---------------- #
daily_adhkar = [
    "سبحان الله وبحمده سبحان الله العظيم",
    "لا إله إلا الله وحده لا شريك له له الملك وله الحمد وهو على كل شيء قدير",
    "اللهم صل وسلم على نبينا محمد",
    "أستغفر الله العظيم وأتوب إليه",
    "اللهم اجعل هذا اليوم بركة وخير لنا ولأحبتنا",
    "اللهم ارزقنا حسن الخاتمة",
    "ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
    "اللهم اجعلنا من الذين يستمعون القول فيتبعون أحسنه",
    "اللهم اجعلنا من التوابين واجعلنا من المتطهرين",
    "اللهم اغفر لنا ذنوبنا وكفر عنا سيئاتنا وتوفنا مع الأبرار"
]

# ---------------- أوامر المساعدة ---------------- #
help_text = "الأوامر المتاحة:\n"
help_text += "1. تسبيح: اكتب 'تسبيح' لمعرفة عدد التسبيحات لكل كلمة\n"
help_text += "2. إرسال كلمة من 'سبحان الله' أو 'الحمد لله' أو 'الله أكبر' لزيادة العدد\n"
help_text += "3. منع الروابط المكررة\n"
help_text += "4. الأدعية المحددة:\n"

for dua_name in specific_duas.keys():
    help_text += f"- {dua_name}\n"

# ---------------- القوائم التلقائية ---------------- #
target_groups = set()
target_users = set()

# ---------------- أذكار تلقائية بدون تكرار ---------------- #
def send_unique_adhkar():
    adhkar_pool = daily_adhkar.copy()
    while True:
        if not adhkar_pool:
            adhkar_pool = daily_adhkar.copy()
        current_adhkar = adhkar_pool.pop(random.randint(0, len(adhkar_pool)-1))
        for group_id in list(target_groups):
            try:
                line_bot_api.push_message(group_id, TextSendMessage(text=current_adhkar))
            except:
                pass
        for user_id in list(target_users):
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=current_adhkar))
            except:
                pass
        time.sleep(5)

threading.Thread(target=send_unique_adhkar, daemon=True).start()

# ---------------- Webhook ---------------- #
@app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    threading.Thread(target=handle_async, args=(body, signature)).start()
    return "OK", 200

def handle_async(body, signature):
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("خطأ في التوقيع")

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # حفظ القروب أو المستخدم تلقائيًا
    if hasattr(event.source, 'group_id'):
        target_groups.add(event.source.group_id)
    elif hasattr(event.source, 'user_id'):
        target_users.add(event.source.user_id)

    # حماية الروابط
    if contains_link(user_text):
        if user_id not in links_count:
            links_count[user_id] = 1
        else:
            if links_count[user_id] == 1:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
            links_count[user_id] = 2
        return

    # تسبيح
    if user_text == "تسبيح":
        ensure_user_counts(user_id)
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        ensure_user_counts(user_id)
        if tasbih_counts[user_id][user_text] < tasbih_limits:
            tasbih_counts[user_id][user_text] += 1
            counts = tasbih_counts[user_id]
            if tasbih_counts[user_id][user_text] >= tasbih_limits:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {user_text} ({tasbih_limits} مرة)"))
            else:
                status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{user_text} مكتمل ({tasbih_limits} مرة)"))
        return

    # الأدعية المحددة
    if user_text in specific_duas:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=specific_duas[user_text]))
        return

    # المساعدة
    if user_text.lower() == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

# ---------------- تشغيل السيرفر ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
