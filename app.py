from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os
import random
import time
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
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"groups": list(target_groups), "users": list(target_users)}, f, ensure_ascii=False, indent=2)

# ---------------- بيانات التسبيح ---------------- #
tasbih_limits = 33
tasbih_counts = {}

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# ---------------- حماية الروابط ---------------- #
links_count = {}

def handle_links(event, user_text, user_id):
    if "http://" in user_text or "https://" in user_text or "www." in user_text:
        if user_id not in links_count:
            links_count[user_id] = 1
            return False  # تجاهل أول رابط
        else:
            links_count[user_id] += 1
            if links_count[user_id] >= 2:
                line_bot_api.reply_message(
                    event.reply_token,
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
    "اللهم ارزقنا رزقاً حلالاً طيباً وبارك لنا فيه",
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
def send_random_adhkar():
    all_ids = list(target_groups) + list(target_users)
    if not all_ids:
        return
    all_adhkar = daily_adhkar + list(specific_duas.values())
    current_adhkar = random.choice(all_adhkar)
    for target_id in all_ids:
        try:
            line_bot_api.push_message(target_id, TextSendMessage(text=current_adhkar))
        except:
            pass

# ---------------- جدولة الإرسال العشوائي ---------------- #
scheduler = BackgroundScheduler()

def schedule_random_times():
    # إرسال بين الساعة 6 صباحًا و 10 مساءً في أوقات عشوائية
    for _ in range(5):  # 5 أوقات يوميًا
        hour = random.randint(6, 22)
        minute = random.randint(0, 59)
        scheduler.add_job(send_random_adhkar, "cron", hour=hour, minute=minute)

schedule_random_times()
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

    # تسجيل المستخدمين والمجموعات تلقائي
    first_time = False
    if hasattr(event.source, 'group_id'):
        target_id = event.source.group_id
        if target_id not in target_groups:
            first_time = True
        target_groups.add(target_id)
    else:
        target_id = user_id
        if target_id not in target_users:
            first_time = True
        target_users.add(target_id)

    save_data()
    ensure_user_counts(user_id)

    # إرسال أذكار أول تواصل فقط
    if first_time:
        try:
            line_bot_api.push_message(target_id, TextSendMessage(text="البوت شغال ✅"))
            send_random_adhkar()
        except:
            pass

    # حماية الروابط
    if handle_links(event, user_text, user_id):
        return

    # الرد على أوامر البوت فقط
    if user_text.lower() == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
