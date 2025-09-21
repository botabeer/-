from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import threading
import random
import time
import re
import json
from datetime import datetime, timedelta

# إعداد البوت
LINE_CHANNEL_ACCESS_TOKEN = "+45+mwHysH3aVwpHoZfxx2TQDClHZW2vTkLTQcUGyjQQX4pEmp5Ofpan0rPzYq/84F/5HNSqqEJ8YeRhmxbKRhPgJMEMQDcFY57RFZ+xjh88NQaQQbh4/WBDIsYucrgLnKzwwXSl0sRbtuJr03+83gdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "21d8b470b71a3b46c700c77b67f1f9ff"
ADMIN_USER_ID = "Ub0345b01633bbe470bb6ca45ed48a913"
PORT = 5000

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# بيانات التسبيح
tasbih_limits = 33
tasbih_counts = {}
links_count = {}
last_sent = {}

# أذكار وأدعية
daily_adhkar = [
    "اللهم اجعل عملي خالصا لوجهك واغفر لي ذنوبي",
    "أستغفر الله العظيم وأتوب إليه",
    "اللهم اهدني لأحسن الأعمال وارزقني التوفيق",
    "اللهم اجعل قلبي مطمئنا بالإيمان",
    "اللهم اغفر لوالديّ وارزقهم الفردوس الأعلى",
    "اللهم ارحم موتانا وموتى المسلمين واجعل قبورهم روضة",
    "اللهم احفظني وأهلي من كل سوء وشر",
    "أعوذ بكلمات الله التامات من شر ما خلق",
    "اللهم ارزقنا رزقا حلالا طيبا واسعا وبارك لنا فيه",
    "اللهم وفقني في حياتي وحقق لي الخير",
    "اللهم احفظ بدني وعقلي وروحي",
    "اللهم اشف مرضانا ومرضى المسلمين",
    "اللهم اجعل قلبي مطمئنا وقريبا منك"
]

specific_duas = {
    "دعاء الموتى": "اللهم ارحم موتانا وموتى المسلمين واجعل قبورهم روضة من رياض الجنة",
    "دعاء الوالدين": "اللهم اغفر لوالديّ وارزقهم الفردوس الأعلى",
    "دعاء النفس": "اللهم اجعل عملي خالصا لوجهك واغفر لي ذنوبي",
    "دعاء التحصين": "اللهم احفظني وأهلي من كل سوء وشر",
    "دعاء الرزق": "اللهم ارزقنا رزقا حلالا طيبا واسعا وبارك لنا فيه",
    "دعاء النجاح": "اللهم وفقني ونجحني في حياتي وحقق لي ما أحب"
}

# أوامر المساعدة
help_text = """
أوامر البوت:

- تسبيح: اكتب 'تسبيح' لمعرفة عدد التسبيحات لكل كلمة
- زيادة التسبيح: أرسل 'سبحان الله' أو 'الحمد لله' أو 'الله أكبر'
- الرد على السلام: أي رسالة تحتوي "السلام" يرد عليها
"""

# القوائم
target_groups = set()
target_users = set()
sent_today = set()

# حفظ/تحميل البيانات
def save_data():
    data = {"groups": list(target_groups), "users": list(target_users)}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_data():
    global target_groups, target_users
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            target_groups = set(data.get("groups", []))
            target_users = set(data.get("users", []))

load_data()

# وظائف
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
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم حذفك بسبب تكرار الروابط"))
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
        time.sleep(3600)

def reset_last_sent_midnight():
    global last_sent
    while True:
        now = datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time.sleep((tomorrow - now).total_seconds())
        last_sent = {}
        if ADMIN_USER_ID:
            try:
                report_text = f"تقرير منتصف الليل:\nعدد القروبات: {len(target_groups)}\nعدد المستخدمين: {len(target_users)}"
                line_bot_api.push_message(ADMIN_USER_ID, TextSendMessage(text=report_text))
            except:
                pass

def send_startup_message():
    if ADMIN_USER_ID:
        random_text = random.choice(daily_adhkar + list(specific_duas.values()))
        try:
            line_bot_api.push_message(ADMIN_USER_ID, TextSendMessage(text=f"تم تشغيل البوت بنجاح\n{random_text}"))
        except:
            pass

# Threads
threading.Thread(target=send_daily_adhkar, daemon=True).start()
threading.Thread(target=reset_last_sent_midnight, daemon=True).start()
threading.Thread(target=send_startup_message, daemon=True).start()

# Webhook
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

# معالجة الرسائل
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    source_type = event.source.type

    if source_type in ["group", "room"]:
        gid = getattr(event.source, "group_id", None) or getattr(event.source, "room_id", None)
        if gid:
            target_groups.add(gid)
            save_data()
            if last_sent.get(gid) != datetime.now().date():
                random_text = random.choice(daily_adhkar + list(specific_duas.values()))
                line_bot_api.push_message(gid, TextSendMessage(text=random_text))
                last_sent[gid] = datetime.now().date()
    elif source_type == "user":
        uid = event.source.user_id
        target_users.add(uid)
        save_data()
        if last_sent.get(uid) != datetime.now().date():
            random_text = random.choice(daily_adhkar + list(specific_duas.values()))
            line_bot_api.push_message(uid, TextSendMessage(text=random_text))
            last_sent[uid] = datetime.now().date()

    # المساعدة
    if user_text.lower() == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # الرد على السلام
    if "السلام" in user_text:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="وعليكم السلام ورحمة الله وبركاته"))
        return

    # حماية الروابط
    if handle_links(event, user_text, event.source.user_id):
        return

    # التسبيح
    ensure_user_counts(event.source.user_id)
    if user_text == "تسبيح":
        counts = tasbih_counts[event.source.user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return
    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        tasbih_counts[event.source.user_id][user_text] += 1
        counts = tasbih_counts[event.source.user_id]
        if counts[user_text] >= tasbih_limits:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {user_text} ({tasbih_limits} مرة)"))
        else:
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
