from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os, threading, random, json, time
from dotenv import load_dotenv

load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

DATA_FILE = "data.json"
target_groups, target_users = set(), set()

def load_data():
    global target_groups, target_users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                target_groups = set(data.get("groups", []))
                target_users = set(data.get("users", []))
        except: pass

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"groups": list(target_groups), "users": list(target_users)}, f, ensure_ascii=False, indent=2)

load_data()

# تحميل الرسائل من ملف خارجي
with open("messages.json", "r", encoding="utf-8") as f:
    messages_data = json.load(f)

tasbih_counts = {}
tasbih_limits = 33
links_count = {}

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

def handle_links(event, user_text, user_id):
    import re
    if re.search(r"(https?://\S+|www\.\S+)", user_text):
        if user_id in links_count:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
        links_count[user_id] = links_count.get(user_id, 0) + 1
        if links_count[user_id] >= 4:
            if user_id in target_users: target_users.remove(user_id)
            save_data()
        return True
    return False

def send_random_message():
    all_ids = list(target_groups) + list(target_users)
    if not all_ids: return
    category = random.choice(list(messages_data.keys()))
    msg = random.choice(messages_data[category])
    for target_id in all_ids:
        try: line_bot_api.push_message(target_id, TextSendMessage(text=msg))
        except: pass

scheduler = BackgroundScheduler()
scheduler.add_job(send_random_message, "interval", minutes=5)
scheduler.start()

@app.route("/", methods=["GET"])
def home(): return "بوت شغال✅", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: print("خطأ في التوقيع")
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    if hasattr(event.source, 'group_id'):
        target_groups.add(event.source.group_id)
    else:
        target_users.add(user_id)
    save_data()
    ensure_user_counts(user_id)

    if handle_links(event, user_text, user_id): return

    if user_text.lower() == "مساعدة":
        cmds = ["مساعدة", "تسبيح", "سبحان الله", "الحمد لله", "الله أكبر"]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="أوامر البوت المتاحة:\n" + "\n".join(cmds)))
        return

    if user_text == "تسبيح":
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله","الحمد لله","الله أكبر"):
        tasbih_counts[user_id][user_text] += 1
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
