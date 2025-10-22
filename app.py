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
            json.dump({"users": [], "groups": [], "tasbih": {}, "notifications_off": []}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}, set()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("users", [])), set(data.get("groups", [])), data.get("tasbih", {}), set(data.get("notifications_off", []))

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": list(target_users),
            "groups": list(target_groups),
            "tasbih": tasbih_counts,
            "notifications_off": list(notifications_off)
        }, f, ensure_ascii=False, indent=2)

target_users, target_groups, tasbih_counts, notifications_off = load_data()

# ---------------- تحميل المحتوى ---------------- #
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# ---------------- إرسال ذكر/دعاء تلقائي ---------------- #
def send_random_message_to_all():
    category = random.choice(["duas", "adhkar", "hadiths"])
    message = random.choice(content.get(category, ["لا يوجد محتوى"]))
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

def scheduled_messages():
    while True:
        send_random_message_to_all()
        time.sleep(random.randint(14400, 18000))  # كل 4-5 ساعات

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

# ---------------- تسبيح ---------------- #
tasbih_limits = 33
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0, "استغفر الله":0}

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id

        # ---------------- تسجيل المستخدمين والقروبات تلقائي ---------------- #
        first_time = False

        if user_id not in target_users:
            target_users.add(user_id)
            first_time = True

        gid = getattr(event.source, 'group_id', None)
        if gid and gid not in target_groups:
            target_groups.add(gid)
            first_time = True

        save_data()
        ensure_user_counts(user_id)

        # ---------------- إرسال ذكر/دعاء عند أول رسالة ---------------- #
        if first_time:
            send_random_message_to_all()
            return

        # ---------------- حماية الروابط ---------------- #
        if handle_links(event, user_id):
            return

        # ---------------- أوامر المساعدة ---------------- #
        if user_text.lower() == "مساعدة":
            try:
                with open("help.txt", "r", encoding="utf-8") as f:
                    help_text = f.read()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
            except:
                pass
            return

        # ---------------- عرض التسبيح ---------------- #
        if user_text.lower() == "تسبيح":
            counts = tasbih_counts[user_id]
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33\nاستغفر الله: {counts['استغفر الله']}/33"
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
            except:
                pass
            return

        # ---------------- التسبيح (زيادة العد حتى 33 فقط) ---------------- #
        if user_text in ("سبحان الله","الحمد لله","الله أكبر","استغفر الله","استغفرالله"):
            key = "استغفر الله" if "استغفر" in user_text else user_text
            if tasbih_counts[user_id][key] < tasbih_limits:
                tasbih_counts[user_id][key] += 1
                save_data()
            counts = tasbih_counts[user_id]
            status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33\nاستغفر الله: {counts['استغفر الله']}/33"
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
            except:
                pass
            return

        # ---------------- إيقاف التذكير ---------------- #
        if user_text.lower() == "إيقاف":
            target_id = gid if gid else user_id
            notifications_off.add(target_id)
            save_data()
            return

        # ---------------- تشغيل التذكير ---------------- #
        if user_text.lower() == "تشغيل":
            target_id = gid if gid else user_id
            if target_id in notifications_off:
                notifications_off.remove(target_id)
                save_data()
            return

        # ---------------- أمر ذكرني ---------------- #
        if user_text.lower() == "ذكرني":
            send_random_message_to_all()
            return

    except:
        pass

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
