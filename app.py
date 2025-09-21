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

# ---------------- حماية الروابط ---------------- #
links_count = {}

def reset_links_count():
    """تصفير العدادات كل 24 ساعة"""
    global links_count
    while True:
        time.sleep(86400)
        links_count = {}

threading.Thread(target=reset_links_count, daemon=True).start()

def handle_links(event, user_text, user_id):
    if re.search(r"(https?://\S+|www\.\S+)", user_text):
        if user_id not in links_count:
            links_count[user_id] = 1
        else:
            links_count[user_id] += 1

            if links_count[user_id] == 2:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ الرجاء عدم تكرار الروابط")
                )
            elif links_count[user_id] >= 4:
                # حذف المستخدم من القوائم
                if user_id in target_users:
                    target_users.remove(user_id)
                if hasattr(event.source, "group_id") and event.source.group_id in target_groups:
                    target_groups.remove(event.source.group_id)

                save_data()

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="🚫 تم حذفك بسبب تكرار الروابط")
                )
        return True
    return False

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

# ---------------- القوائم ---------------- #
target_groups, target_users = load_data()
sent_today = set()

# ---------------- إرسال تلقائي ---------------- #
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

    # تخزين القروبات والمستخدمين
    if hasattr(event.source, 'group_id'):
        target_groups.add(event.source.group_id)
        save_data()
    elif hasattr(event.source, 'user_id'):
        target_users.add(event.source.user_id)
        save_data()

    # رد السلام
    if re.search(r"السلام", user_text, re.IGNORECASE):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="وعليكم السلام ورحمة الله وبركاته"))
        return

    # حماية الروابط
    if handle_links(event, user_text, user_id):
        return

    # أمر إرسال للكل
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
