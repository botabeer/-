from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
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
tasbih_counts = {}

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# ---------------- حماية الروابط ---------------- #
links_count = {}

def handle_links(event, user_text, user_id):
    if re.search(r"(https?://\S+|www\.\S+)", user_text):
        if user_id not in links_count:
            links_count[user_id] = 1  # أول رابط
        else:
            links_count[user_id] += 1
            if links_count[user_id] == 2:  # التحذير عند المرة الثانية
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="الرجاء عدم تكرار الروابط")
                )
            elif links_count[user_id] >= 4:  # الحذف عند المرة الرابعة
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="سيتم حذفك من الإدارة لتكرار الروابط")
                )
        return True
    return False

# ---------------- أذكار وأدعية شاملة ---------------- #
daily_adhkar = [
    "اللهم اجعل عملي خالصاً لوجهك واغفر لي ذنوبي",
    "أستغفر الله العظيم الذي لا إله إلا هو الحي القيوم وأتوب إليه",
    "اللهم اهدني لأحسن الأعمال وارزقني التوفيق",
    "اللهم اجعل قلبي مطمئناً بالإيمان",
    "اللهم اجعل لي نوراً في قلبي وطمأنينة في نفسي",
    "اللهم اغفر لوالديّ وارزقهم الفردوس الأعلى واجعلهم من السعداء في الآخرة",
    "اللهم اجعل والدينا من الذين يُستجاب لهم دعاؤهم واغفر لهم",
    "اللهم ارحم موتانا وموتى المسلمين واجعل قبورهم روضة من رياض الجنة",
    "اللهم اغفر لهم وتجاوز عن سيئاتهم وانزلهم منزلاً كريمًا",
    "اللهم احفظني وأهلي من كل سوء وشر وكن لنا حصناً من كل عين وحسد",
    "أعوذ بكلمات الله التامات من شر ما خلق",
    "اللهم اجعلنا من المحصنين بعينك التي لا تنام",
    "اللهم ارزقنا رزقاً حلالاً طيباً واسعاً وبارك لنا فيه",
    "اللهم اجعلنا من الشاكرين لنعيمك وبارك لنا في رزقنا",
    "اللهم ارزقني الغنى الحلال ووسع علي رزقي",
    "اللهم وفقني في دراستي وعمالي وحقق لي الخير",
    "اللهم اجعلني من الناجحين المتفوقين في كل أموري",
    "اللهم افتح لي أبواب التوفيق والرزق في حياتي",
    "اللهم احفظ بدني وعقلي وروحي",
    "اللهم اشف مرضانا ومرضى المسلمين",
    "اللهم اجعلنا من الآمنين من كل بلاء ووباء",
    "اللهم ارزقني الصبر والرضا بقضائك",
    "اللهم اجعل قلبي مطمئناً وقريباً منك",
    "اللهم اجعلني من الذين يستمعون القول فيتبعون أحسنه"
]

specific_duas = {
    "دعاء الموتى": "اللهم ارحم موتانا وموتى المسلمين واجعل قبورهم روضة من رياض الجنة",
    "دعاء الوالدين": "اللهم اغفر لوالديّ وارزقهم الفردوس الأعلى واجعلهم من السعداء في الآخرة",
    "دعاء النفس": "اللهم اجعل عملي خالصاً لوجهك واغفر لي ذنوبي واهدني لأحسن الأعمال",
    "دعاء التحصين": "اللهم احفظني وأهلي من كل سوء وشر، وكن لنا حصناً من كل عين وحسد",
    "دعاء الوقاية": "أعوذ بكلمات الله التامات من شر ما خلق",
    "دعاء الرزق": "اللهم ارزقنا رزقاً حلالاً طيباً واسعاً وبارك لنا فيه",
    "دعاء البركة في الرزق": "اللهم اجعلنا من الشاكرين لنعيمك وبارك لنا في رزقنا",
    "دعاء النجاح": "اللهم وفقني ونجحني في حياتي وحقّق لي ما أحب",
    "دعاء الصحة": "اللهم احفظ بدني وعقلي وروحي وامنحنا الصحة والسلامة",
    "دعاء الطمأنينة": "اللهم اجعل قلبي مطمئناً وقريباً منك وارزقني الصبر والرضا"
}

# ---------------- أوامر المساعدة ---------------- #
help_text = """
╔═══════════════
      أوامر البوت
╚═══════════════

- تسبيح:
  اكتب 'تسبيح' لمعرفة عدد التسبيحات لكل كلمة

- زيادة التسبيح:
  أرسل كلمة من 'سبحان الله' أو 'الحمد لله' أو 'الله أكبر'
"""

# ---------------- القوائم التلقائية ---------------- #
target_groups = set()
target_users = set()
sent_today = set()

# ---------------- إرسال أذكار وأدعية تلقائية ---------------- #
def send_daily_adhkar():
    while True:
        remaining = [d for d in daily_adhkar if d not in sent_today]
        if not remaining:
            sent_today.clear()
            remaining = daily_adhkar.copy()
        current_adhkar = random.choice(remaining)
        sent_today.add(current_adhkar)

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
        time.sleep(3600)  # كل ساعة

threading.Thread(target=send_daily_adhkar, daemon=True).start()

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

    # حفظ القروبات والمستخدمين تلقائيًا
    if hasattr(event.source, 'group_id'):
        target_groups.add(event.source.group_id)
    elif hasattr(event.source, 'user_id'):
        target_users.add(event.source.user_id)

    # الرد على السلام
    if re.search(r"السلام", user_text, re.IGNORECASE):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="وعليكم السلام ورحمة الله وبركاته"))
        return

    # حماية الروابط
    if handle_links(event, user_text, user_id):
        return

    # التسبيح
    if user_text == "تسبيح":
        ensure_user_counts(user_id)
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        ensure_user_counts(user_id)
        if tasbih_counts[user_id][user_text] < tasbih_counts:
            tasbih_counts[user_id][user_text] += 1
        counts = tasbih_counts[user_id]
        if tasbih_counts[user_id][user_text] >= tasbih_limits:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {user_text} ({tasbih_limits} مرة)"))
        else:
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    # أمر إرسال دعاء أو ذكر عشوائي لكل القروبات والمستخدمين
    if user_text.lower() == "أرسل للكل":
        all_adhkar = daily_adhkar + list(specific_duas.values())
        random_text = random.choice(all_adhkar)
        for group_id in list(target_groups):
            try:
                line_bot_api.push_message(group_id, TextSendMessage(text=random_text))
            except:
                pass
        for uid in list(target_users):
            try:
                line_bot_api.push_message(uid, TextSendMessage(text=random_text))
            except:
                pass
        return
