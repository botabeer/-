from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time
from dotenv import load_dotenv

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
        return set(data.get("groups", [])), set(data.get("users", [])), data.get("tasbih", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"groups": list(target_groups), "users": list(target_users), "tasbih": tasbih_counts}, f, ensure_ascii=False, indent=2)

target_groups, target_users, tasbih_counts = load_data()

with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# ---------------- إرسال عشوائي ---------------- #
def send_random_message():
    category = random.choice(["duas", "verses", "hadiths"])
    message = random.choice(content[category])
    all_ids = list(target_groups) + list(target_users)
    for tid in all_ids:
        try:
            line_bot_api.push_message(tid, TextSendMessage(text=message))
        except:
            pass

def message_loop():
    while True:
        send_random_message()
        time.sleep(random.randint(3600,5400))

threading.Thread(target=message_loop, daemon=True).start()

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

# ---------------- حماية الروابط ---------------- #
links_count = {}
def handle_links(event, user_id):
    text = event.message.text.strip()
    if "http://" in text or "https://" in text or "www." in text:
        if user_id not in links_count:
            links_count[user_id] = 1
        else:
            links_count[user_id] += 1
        if links_count[user_id] >= 2:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
        return True
    return False

# ---------------- تسبيح ---------------- #
tasbih_limits = 33
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0}

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.source.type == "user":
        target_id = event.source.user_id
        if target_id not in target_users:
            target_users.add(target_id)
            message = random.choice(content[random.choice(["duas","verses","hadiths"])])
            line_bot_api.push_message(target_id, TextSendMessage(text=message))
    elif event.source.type == "group":
        target_id = event.source.group_id
        if target_id not in target_groups:
            target_groups.add(target_id)
            message = random.choice(content[random.choice(["duas","verses","hadiths"])])
            line_bot_api.push_message(target_id, TextSendMessage(text=message))
    else:
        return
    save_data()
    ensure_user_counts(target_id)
    if handle_links(event, target_id):
        return
    user_text = event.message.text.strip()
    if user_text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الأوامر: تسبيح، سبحان الله، الحمد لله، الله أكبر"))
        return
    if user_text == "تسبيح":
        counts = tasbih_counts[target_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return
    if user_text in ("سبحان الله","الحمد لله","الله أكبر"):
        tasbih_counts[target_id][user_text] += 1
        save_data()
        counts = tasbih_counts[target_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
