from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time, re
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
            json.dump({"users": [], "groups": [], "tasbih": {}, "links": {}, "notifications": {}}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}, {}, {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("groups", [])), set(data.get("users", [])), data.get("tasbih", {}), data.get("links", {}), data.get("notifications", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "groups": list(target_groups),
            "users": list(target_users),
            "tasbih": tasbih_counts,
            "links": user_links,
            "notifications": notifications
        }, f, ensure_ascii=False, indent=2)

target_groups, target_users, tasbih_counts, user_links, notifications = load_data()

# ---------------- تحميل المحتوى ---------------- #
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# ---------------- إرسال رسائل عشوائية ---------------- #
def send_random_message():
    category = random.choice(["duas", "adhkar", "hadiths"])
    message = random.choice(content[category])
    all_ids = list(target_groups) + list(target_users)
    for tid in all_ids:
        if notifications.get(tid, True):  # تحقق من إذا المستخدم/القروب مفعل عنده الإشعارات
            try:
                line_bot_api.push_message(tid, TextSendMessage(text=message))
            except:
                pass

def message_loop():
    while True:
        send_random_message()
        time.sleep(random.randint(3600,5400))  # كل ساعة إلى ساعة ونصف

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

# ---------------- تسبيح ---------------- #
tasbih_limits = 33
def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0}

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    target_id = user_id if not hasattr(event.source, "group_id") else event.source.group_id
    first_time = False

    # تسجيل المستخدمين والقروبات لأول مرة
    if hasattr(event.source, "group_id") and event.source.group_id:
        if target_id not in target_groups:
            first_time = True
        target_groups.add(target_id)
    else:
        if target_id not in target_users:
            first_time = True
        target_users.add(target_id)
    save_data()
    ensure_user_counts(user_id)
    if target_id not in notifications:
        notifications[target_id] = True

    # إرسال رسالة عشوائية أول تواصل
    if first_time and notifications.get(target_id, True):
        message = random.choice(content["duas"] + content["adhkar"] + content["hadiths"])
        line_bot_api.push_message(target_id, TextSendMessage(text=message))

    # حماية الروابط
    url_pattern = r"(https?://[^\s]+|www\.[^\s]+)"
    urls_found = re.findall(url_pattern, user_text)
    if urls_found:
        user_links.setdefault(user_id, [])
        duplicate = False
        for url in urls_found:
            if url in user_links[user_id]:
                duplicate = True
            else:
                user_links[user_id].append(url)
        if duplicate:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
        save_data()
        return

    # أوامر
    if user_text.lower() == "مساعدة":
        help_text = (
            "أوامر البوت:\n"
            "1. مساعدة - عرض قائمة الأوامر.\n"
            "2. ذكرني - يبدأ الإشعارات التلقائية للكل.\n"
            "3. إيقاف - يوقف الإشعارات التلقائية.\n"
            "4. تشغيل - يعيد تفعيل الإشعارات التلقائية.\n"
            "5. تسبيح - عرض عدد التسبيحات لكل كلمة."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if user_text.lower() == "ذكرني":
        send_random_message()
        return

    if user_text.lower() == "إيقاف":
        notifications[target_id] = False
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف الإشعارات التلقائية."))
        return

    if user_text.lower() == "تشغيل":
        notifications[target_id] = True
        save_data()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إعادة تفعيل الإشعارات التلقائية."))
        return

    if user_text.lower() == "تسبيح":
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return

    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        tasbih_counts[user_id][user_text] += 1
        save_data()
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
