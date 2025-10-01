from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os
import threading
import random
import time
import re
import json
from dotenv import load_dotenv

# ---------------- إعداد البوت ---------------- #
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- ملف التخزين ---------------- #
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": [], "users": []}, f, ensure_ascii=False, indent=2)
        return set(), set()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("groups", [])), set(data.get("users", []))
    except:
        return set(), set()

def save_data():
    data = {
        "groups": list(target_groups),
        "users": list(target_users)
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------- بيانات التسبيح ---------------- #
tasbih_limits = 33
tasbih_counts = {}

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# ---------------- حماية الروابط ---------------- #
links_count = {}

def handle_links(user_id, user_text, reply_token):
    if re.search(r"(https?://\S+|www\.\S+)", user_text):
        if user_id not in links_count:
            links_count[user_id] = 1
        else:
            links_count[user_id] += 1

        if links_count[user_id] == 2:
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="الرجاء عدم تكرار الروابط")
            )
        return True
    return False

# ---------------- أذكار وأدعية ---------------- #
daily_adhkar = [
    "اللهم اجعل عملي خالصاً لوجهك واغفر لي ذنوبي",
    "أستغفر الله العظيم وأتوب إليه",
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
أوامر البوت المتاحة:

1. مساعدة
   - عرض قائمة الأوامر.

2. تسبيح
   - عرض عدد التسبيحات لكل كلمة لكل مستخدم.

3. سبحان الله / الحمد لله / الله أكبر
   - زيادة عدد التسبيحات لكل كلمة.
"""

# ---------------- القوائم ---------------- #
target_groups, target_users = load_data()

# ---------------- إرسال الأذكار ---------------- #
def send_random_adhkar_to(target_id):
    all_adhkar = daily_adhkar + list(specific_duas.values())
    current_adhkar = random.choice(all_adhkar)
    try:
        line_bot_api.push_message(target_id, TextSendMessage(text=current_adhkar))
    except:
        pass

def send_morning_adhkar():
    for target_id in list(target_groups) + list(target_users):
        send_random_adhkar_to(target_id)

def send_evening_adhkar():
    for target_id in list(target_groups) + list(target_users):
        send_random_adhkar_to(target_id)

def send_sleep_adhkar():
    for target_id in list(target_groups) + list(target_users):
        send_random_adhkar_to(target_id)

# ---------------- جدولة الإرسال ---------------- #
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: [send_random_adhkar_to(tid) for tid in list(target_groups) + list(target_users)], "interval", minutes=1)

# أوقات محددة
for hour in [6, 10, 14, 18, 22]:
    scheduler.add_job(lambda: [send_random_adhkar_to(tid) for tid in list(target_groups) + list(target_users)], "cron", hour=hour, minute=0)

scheduler.add_job(send_morning_adhkar, "cron", hour=5, minute=0)
scheduler.add_job(send_evening_adhkar, "cron", hour=17, minute=0)
scheduler.add_job(send_sleep_adhkar, "cron", hour=22, minute=0)

scheduler.start()

# ---------------- Webhook ---------------- #
@app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("خطأ في التوقيع")
    return "OK", 200

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    first_time = False

    # تسجيل المستخدمين والقروبات تلقائي
    if hasattr(event.source, 'group_id'):
        target_id = event.source.group_id
        if target_id not in target_groups:
            target_groups.add(target_id)
            first_time = True
    else:
        target_id = user_id
        if user_id not in target_users:
            target_users.add(user_id)
            first_time = True

    save_data()
    ensure_user_counts(user_id)

    # إذا كان أول مرة، أرسل ذكر أو دعاء مباشرة
    if first_time:
        send_random_adhkar_to(target_id)

    # المساعدة
    if user_text.lower() == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # التسبيح
    if user_text == "تسبيح":
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        tasbih_counts[user_id][user_text] += 1
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    # حماية الروابط
    handle_links(user_id, user_text, event.reply_token)

    # إرسال ذكر عشوائي عند أي رسالة
    message = random.choice(daily_adhkar)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
