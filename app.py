from flask import Flask, request
from linebot.v3.messaging import MessagingApi
from linebot.exceptions import LineBotApiError
from linebot.models import MessageEvent, TextMessage
import os, random, json, threading, time, logging
from dotenv import load_dotenv

# ================= إعداد التسجيل =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= إعداد البوت =================
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
PORT = int(os.getenv("PORT", 5000))

messaging_api = MessagingApi(channel_access_token=LINE_CHANNEL_ACCESS_TOKEN)

# ================= ملفات البيانات =================
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"
FADL_FILE = "fadl.json"

# ================= تحميل بيانات فضل =================
def load_fadl_content():
    if not os.path.exists(FADL_FILE):
        with open(FADL_FILE, "w", encoding="utf-8") as f:
            json.dump({"fadl": ["لا يوجد فضل بعد الآن"]}, f, ensure_ascii=False, indent=2)
        logger.info(f"{FADL_FILE} لم يكن موجودًا، تم إنشاؤه تلقائيًا")
    try:
        with open(FADL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("fadl", [])
    except Exception as e:
        logger.error(f"خطأ في تحميل {FADL_FILE}: {e}")
        return []

# ================= تحميل البيانات =================
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": [], "groups": [], "tasbih": {}}, f, ensure_ascii=False, indent=2)
        return set(), set(), {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("users", [])), set(data.get("groups", [])), data.get("tasbih", {})
    except Exception as e:
        logger.error(f"خطأ في تحميل البيانات: {e}")
        return set(), set(), {}

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "users": list(target_users),
                "groups": list(target_groups),
                "tasbih": tasbih_counts
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ البيانات: {e}")

target_users, target_groups, tasbih_counts = load_data()
fadl_content = load_fadl_content()

# ================= تحميل محتوى الدعاء والأذكار =================
def load_content():
    try:
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل {CONTENT_FILE}: {e}")
        return {"duas": [], "adhkar": [], "hadiths": [], "quran": []}

content = load_content()

# ================= دوال مساعدة =================
def safe_send_message(target_id, message):
    try:
        messaging_api.push_message(to=target_id, messages=[{"type": "text", "text": message}])
        return True
    except LineBotApiError as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
        return False

def safe_reply_silent_fail(reply_token, message):
    try:
        messaging_api.reply_message(reply_token=reply_token, messages=[{"type": "text", "text": message}])
        return True
    except LineBotApiError as e:
        logger.error(f"خطأ في الرد: {e}")
        return False

def get_user_display_name(user_id):
    try:
        profile = messaging_api.get_profile(user_id)
        return profile.display_name
    except LineBotApiError:
        return "المستخدم"

def get_group_member_display_name(group_id, user_id):
    try:
        profile = messaging_api.get_group_member_profile(group_id, user_id)
        return profile.display_name
    except LineBotApiError:
        return "المستخدم"

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"استغفر الله": 0, "سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}
        save_data()

def get_tasbih_status(user_id, gid=None):
    counts = tasbih_counts[user_id]
    display_name = get_group_member_display_name(gid, user_id) if gid else get_user_display_name(user_id)
    return (
        f"حالة التسبيح\n{display_name}\n\n"
        f"استغفر الله: {counts['استغفر الله']}/33\n"
        f"سبحان الله: {counts['سبحان الله']}/33\n"
        f"الحمد لله: {counts['الحمد لله']}/33\n"
        f"الله أكبر: {counts['الله أكبر']}/33"
    )

# ================= إرسال رسائل تلقائية =================
def send_random_message_to_all():
    try:
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if not messages:
            logger.warning(f"لا يوجد محتوى في الفئة {category}")
            return

        message = random.choice(messages)
        sent_count = 0

        for uid in list(target_users):
            if safe_send_message(uid, message):
                sent_count += 1

        for gid in list(target_groups):
            if safe_send_message(gid, message):
                sent_count += 1

        logger.info(f"تم إرسال رسالة تلقائية إلى {sent_count} مستخدم/مجموعة")
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسائل التلقائية: {e}")

def scheduled_messages():
    while True:
        try:
            send_random_message_to_all()
            sleep_time = random.randint(14400, 18000)  # 4-5 ساعات
            logger.info(f"الرسالة التلقائية القادمة بعد {sleep_time//3600} ساعة")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"خطأ في جدولة الرسائل: {e}")
            time.sleep(3600)

threading.Thread(target=scheduled_messages, daemon=True).start()

# ================= حماية الروابط =================
links_count = {}
def handle_links(event, user_id, gid=None):
    try:
        text = event.message.text.strip()
        if any(x in text.lower() for x in ["http://", "https://", "www."]):
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] == 2:
                display_name = get_group_member_display_name(gid, user_id) if gid else get_user_display_name(user_id)
                warning_msg = f"{display_name}\nالرجاء عدم تكرار إرسال الروابط"
                safe_reply_silent_fail(event.reply_token, warning_msg)
                logger.info(f"تحذير المستخدم {user_id} من تكرار الروابط")
                return True
            elif links_count[user_id] >= 3:
                logger.info(f"تم تجاهل رابط متكرر من المستخدم {user_id}")
                return True
            return True
    except Exception as e:
        logger.error(f"خطأ في معالجة الروابط: {e}")
    return False

# ================= معالجة الرسائل =================
@app.route("/callback", methods=["POST"])
def callback():
    try:
        body = request.get_data(as_text=True)
        events = json.loads(body).get("events", [])
        for event in events:
            if event["type"] == "message" and event["message"]["type"] == "text":
                user_id = event["source"]["userId"]
                gid = event["source"].get("groupId")
                user_text = event["message"]["text"].strip()

                if user_id not in target_users:
                    target_users.add(user_id)
                    save_data()

                if gid and gid not in target_groups:
                    target_groups.add(gid)
                    save_data()

                ensure_user_counts(user_id)
                if handle_links(event, user_id, gid):
                    continue

                text_lower = user_text.lower()

                if text_lower == "فضل" and fadl_content:
                    safe_reply_silent_fail(event["replyToken"], random.choice(fadl_content))
                    continue

                if text_lower == "تسبيح":
                    status = get_tasbih_status(user_id, gid)
                    safe_reply_silent_fail(event["replyToken"], status)
                    continue

                if text_lower == "ذكرني":
                    category = random.choice(["duas", "adhkar", "hadiths", "quran"])
                    messages = content.get(category, [])
                    if messages:
                        message = random.choice(messages)
                        safe_reply_silent_fail(event["replyToken"], message)
                        for uid in target_users:
                            safe_send_message(uid, message)
                        for g in target_groups:
                            safe_send_message(g, message)
                    continue

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسائل: {e}")

# ================= Web =================
@app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200

# ================= تشغيل التطبيق =================
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
