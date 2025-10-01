from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os
import threading
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
CONTENT_FILE = "content.json"  # ملف الأذكار والأدعية والآيات

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

# ---------------- تحميل المحتوى ---------------- #
def load_content():
    if os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"adhkar": [], "duas": [], "quran": [], "ahadith": []}

content = load_content()

# ---------------- بيانات التسبيح ---------------- #
tasbih_limits = 33
tasbih_counts = {}

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# ---------------- حماية الروابط ---------------- #
links_count = {}

def handle_links(event, user_text, user_id):
    import re
    if re.search(r"(https?://\S+|www\.\S+)", user_text):
        if user_id in links_count:
            links_count[user_id] += 1
            if links_count[user_id] >= 2:
                line_bot_api.reply_message(event.reply_token,
                                           TextSendMessage(text="الرجاء عدم تكرار الروابط"))
        else:
            links_count[user_id] = 1
        if links_count[user_id] > 4:
            if user_id in target_users:
                target_users.remove(user_id)
            save_data()
        return True
    return False

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

# ---------------- إرسال المحتوى ---------------- #
scheduler = BackgroundScheduler()

def send_random_message():
    all_ids = list(target_groups) + list(target_users)
    if not all_ids:
        return
    all_content = content["adhkar"] + content["duas"] + content["quran"] + content["ahadith"]
    message = random.choice(all_content)
    for target_id in all_ids:
        try:
            line_bot_api.push_message(target_id, TextSendMessage(text=message))
        except:
            pass

# إرسال تذكير تلقائي عند أول رسالة
first_run_done = False

# إرسال متفرقة كل 30-90 دقيقة
def schedule_random_messages():
    send_random_message()
    interval = random.randint(30, 90) * 60
    threading.Timer(interval, schedule_random_messages).start()

schedule_random_messages()

# ---------------- Webhook ---------------- #
@app.route("/", methods=["GET"])
def home():
    return "البوت شغال ✅", 200

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
    global first_run_done
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # تسجيل المستخدمين والقروبات تلقائي
    if hasattr(event.source, 'group_id'):
        target_groups.add(event.source.group_id)
    else:
        target_users.add(user_id)
    save_data()

    ensure_user_counts(user_id)

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
    handle_links(event, user_text, user_id)

    # إرسال تذكير تلقائي عند أول رسالة
    if not first_run_done:
        first_run_done = True
        send_random_message()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="البوت شغال ✅"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
