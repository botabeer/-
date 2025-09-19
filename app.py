from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import threading
import random
import time
import re
from dotenv import load_dotenv

# ---------------- إعداد البوت ---------------- #
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- بيانات التسبيح ---------------- #
tasbih_limits = 33
tasbih_counts = {}
links_count = {}

# ---------------- أذكار وأدعية ---------------- #
daily_adhkar = [
    "اللهم اجعل عملي خالصاً لوجهك واغفر لي ذنوبي",
    "أستغفر الله العظيم وأتوب إليه",
    "اللهم اهدني لأحسن الأعمال وارزقني التوفيق",
    "اللهم اجعل قلبي مطمئناً بالإيمان",
    "اللهم اغفر لوالديّ وارزقهم الفردوس الأعلى",
    "اللهم ارحم موتانا وموتى المسلمين واجعل قبورهم روضة",
    "اللهم احفظني وأهلي من كل سوء وشر",
    "أعوذ بكلمات الله التامات من شر ما خلق",
    "اللهم ارزقنا رزقاً حلالاً طيباً واسعاً وبارك لنا فيه",
    "اللهم وفقني في حياتي وحقق لي الخير",
    "اللهم احفظ بدني وعقلي وروحي",
    "اللهم اشف مرضانا ومرضى المسلمين",
    "اللهم اجعل قلبي مطمئناً وقريباً منك"
]

specific_duas = {
    "دعاء الموتى": "اللهم ارحم موتانا وموتى المسلمين واجعل قبورهم روضة من رياض الجنة",
    "دعاء الوالدين": "اللهم اغفر لوالديّ وارزقهم الفردوس الأعلى",
    "دعاء النفس": "اللهم اجعل عملي خالصاً لوجهك واغفر لي ذنوبي",
    "دعاء التحصين": "اللهم احفظني وأهلي من كل سوء وشر",
    "دعاء الرزق": "اللهم ارزقنا رزقاً حلالاً طيباً واسعاً وبارك لنا فيه",
    "دعاء النجاح": "اللهم وفقني ونجحني في حياتي وحقّق لي ما أحب"
}

# ---------------- أوامر المساعدة ---------------- #
help_text = """
أوامر البوت:

- تسبيح: اكتب 'تسبيح' لمعرفة عدد التسبيحات لكل كلمة
- زيادة التسبيح: أرسل 'سبحان الله' أو 'الحمد لله' أو 'الله أكبر'
"""

# ---------------- القوائم ---------------- #
target_groups = set()
target_users = set()
sent_today = set()

# ---------------- وظائف ---------------- #
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

def handle_links(event, user_text, user_id):
    if re.search(r"(https?://\S+|www\.\S+)", user_text):
        if user_id not in links_count:
            links_count[user_id] = 1
        else:
            links_count[user_id] += 1
            if links_count[user_id] == 2:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
            elif links_count[user_id] >= 4:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="سيتم حذفك من الإدارة لتكرار الروابط"))
        return True
    return False

def send_daily_adhkar():
    while True:
        if not target_groups and not target_users:
            time.sleep(10)
            continue

        all_adhkar = daily_adhkar + list(specific_duas.values())
        remaining = [d for d in all_adhkar if d not in sent_today]
        if not remaining:
            sent_today.clear()
            remaining = all_adhkar.copy()

        current_adhkar = random.choice(remaining)
        sent_today.add(current_adhkar)

        for group_id in list(target_groups):
            try:
                line_bot_api.push_message(group_id, TextSendMessage(text=current_adhkar))
            except:
                pass
        for uid in list(target_users):
            try:
                line_bot_api.push_message(uid, TextSendMessage(text=current_adhkar))
            except:
                pass

        time.sleep(3600)  # كل ساعة

# بدء الإرسال التلقائي
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

    if hasattr(event.source, 'group_id'):
        target_groups.add(event.source.group_id)
    elif hasattr(event.source, 'user_id'):
        target_users.add(event.source.user_id)

    # المساعدة
    if user_text.strip().lower() == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # الرد على السلام
    if re.search(r"السلام", user_text, re.IGNORECASE):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="وعليكم السلام ورحمة الله وبركاته"))
        return

    # حماية الروابط
    if handle_links(event, user_text, user_id):
        return

    # التسبيح
    ensure_user_counts(user_id)
    if user_text == "تسبيح":
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        tasbih_counts[user_id][user_text] += 1
        counts = tasbih_counts[user_id]
        if tasbih_counts[user_id][user_text] >= tasbih_limits:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {user_text} ({tasbih_limits} مرة)"))
        else:
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    # أي شخص يرسل "أرسل للكل"
    if user_text.lower() == "أرسل للكل":
        all_adhkar = daily_adhkar + list(specific_duas.values())
        random_text = random.choice(all_adhkar)
        for group_id in target_groups:
            try:
                line_bot_api.push_message(group_id, TextSendMessage(text=random_text))
            except:
                pass
        for uid in target_users:
            try:
                line_bot_api.push_message(uid, TextSendMessage(text=random_text))
            except:
                pass
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
