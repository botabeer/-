from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time
from dotenv import load_dotenv

# ---------------- إعداد البوت ---------------- #
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- ملفات البيانات ---------------- #
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": [], "groups": [], "tasbih": {}}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("users", [])), set(data.get("groups", [])), data.get("tasbih", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": list(target_users),
            "groups": list(target_groups),
            "tasbih": tasbih_counts
        }, f, ensure_ascii=False, indent=2)

target_users, target_groups, tasbih_counts = load_data()

# ---------------- محتوى الأذكار والأدعية ---------------- #
all_adhkar = ["سبحان الله","الحمد لله","الله أكبر","استغفر الله"]

# تحميل محتوى إضافي (أدعية، أذكار عامة، أحاديث)
content = {}
if os.path.exists(CONTENT_FILE):
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)

# ---------------- دوال التسبيح ---------------- #
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key:0 for key in all_adhkar}

def send_tasbih_for_user(uid):
    ensure_user_counts(uid)
    remaining_adhkar = [key for key, val in tasbih_counts[uid].items() if val < 33]
    if not remaining_adhkar:
        try:
            line_bot_api.push_message(uid, TextSendMessage(text="لقد أكملت 33 لكل الأذكار!"))
        except:
            pass
        return
    selected = random.choice(remaining_adhkar)
    tasbih_counts[uid][selected] += 1
    save_data()
    try:
        line_bot_api.push_message(uid, TextSendMessage(text=f"{selected} ({tasbih_counts[uid][selected]}/33)"))
    except:
        pass

# ---------------- إرسال رسائل عشوائية ---------------- #
def send_random_content_to_all():
    category = random.choice(["duas","adhkar","hadiths"])
    message = "لا يوجد محتوى"
    if category in content and content[category]:
        message = random.choice(content[category])
    for uid in target_users:
        try:
            line_bot_api.push_message(uid, TextSendMessage(text=message))
        except:
            pass
    for gid in target_groups:
        try:
            line_bot_api.push_message(gid, TextSendMessage(text=message))
        except:
            pass

# ---------------- التذكير التلقائي ---------------- #
def scheduled_messages():
    while True:
        send_random_content_to_all()
        time.sleep(5*60*60)  # تقريباً كل 5 ساعات

threading.Thread(target=scheduled_messages, daemon=True).start()

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
        pass
    return "OK", 200

# ---------------- حماية الروابط ---------------- #
links_count = {}
def handle_links(event, user_id):
    try:
        text = event.message.text.strip()
        if "http://" in text or "https://" in text or "www." in text:
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] >= 2:
                try:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
                except:
                    pass
            return True
    except:
        pass
    return False

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id

        # تسجيل المستخدمين والقروبات تلقائي
        first_time = False
        if user_id not in target_users:
            target_users.add(user_id)
            first_time = True
        gid = getattr(event.source, 'group_id', None)
        if gid and gid not in target_groups:
            target_groups.add(gid)
            first_time = True
        save_data()

        # حماية الروابط
        if handle_links(event, user_id):
            return

        # أمر ذكرني: يرسل محتوى عشوائي
        if user_text.lower() == "ذكرني":
            send_random_content_to_all()
            return

        # أمر تسبيح: يبدأ العد لكل ذكر حتى 33
        if user_text.lower() == "تسبيح":
            send_tasbih_for_user(user_id)
            return

        # أمر مساعدة: يقرأ من ملف help.txt
        if user_text.lower() == "مساعدة":
            try:
                with open("help.txt", "r", encoding="utf-8") as f:
                    help_text = f.read()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
            except:
                pass
            return

    except:
        pass

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
