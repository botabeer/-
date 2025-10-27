from flask import Flask, request
from linebot.v3.webhook import WebhookHandler
from linebot.v3 import LineBotApi
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
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
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(channel_access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(channel_secret=LINE_CHANNEL_SECRET)

# ================= ملفات البيانات =================
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"
FADL_FILE = "fadl.json"

# ================= تحميل بيانات فضل =================
def load_fadl_content():
    if not os.path.exists(FADL_FILE):
        with open(FADL_FILE, "w", encoding="utf-8") as f:
            json.dump({"fadl": []}, f, ensure_ascii=False, indent=2)
        logger.info(f"{FADL_FILE} لم يكن موجودًا، تم إنشاؤه تلقائيًا")
        return []

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
        line_bot_api.push_message(target_id, TextSendMessage(text=message))
        return True
    except:
        return False

def safe_reply_silent_fail(reply_token, message):
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=message))
        return True
    except:
        return False

def get_user_display_name(user_id):
    try:
        profile = line_bot_api.get_profile(user_id)
        return profile.display_name
    except:
        return "المستخدم"

def get_group_member_display_name(group_id, user_id):
    try:
        profile = line_bot_api.get_group_member_profile(group_id, user_id)
        return profile.display_name
    except:
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
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, "group_id", None)

        # ================= تسجيل المستخدمين والمجموعات =================
        if user_id not in target_users:
            target_users.add(user_id)
            save_data()
            logger.info(f"تم تسجيل مستخدم جديد: {user_id}")

        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()
            logger.info(f"تم تسجيل مجموعة جديدة: {gid}")

        ensure_user_counts(user_id)

        # ================= حماية الروابط =================
        if handle_links(event, user_id, gid):
            return

        # ================= أمر فضل =================
        text_lower = user_text.lower()
        if text_lower == "فضل" and fadl_content:
            safe_reply_silent_fail(event.reply_token, random.choice(fadl_content))
            return

        # ================= أمر عرض التسبيح =================
        if text_lower == "تسبيح":
            status = get_tasbih_status(user_id, gid)
            safe_reply_silent_fail(event.reply_token, status)
            return

        # ================= التسبيح =================
        clean_text = user_text.replace(" ", "").replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        key_map = {
            "سبحانالله": "سبحان الله",
            "سبحاناللة": "سبحان الله",
            "الحمدلله": "الحمد لله",
            "الحمدللة": "الحمد لله",
            "اللهأكبر": "الله أكبر",
            "اللهاكبر": "الله أكبر",
            "اللةأكبر": "الله أكبر",
            "اللةاكبر": "الله أكبر",
            "استغفرالله": "استغفر الله",
            "استغفراللة": "استغفر الله"
        }

        key = key_map.get(clean_text)
        if key:
            counts = tasbih_counts[user_id]

            if counts[key] >= 33:
                safe_reply_silent_fail(event.reply_token, f"تم اكتمال {key} مسبقا")
                return

            counts[key] += 1
            save_data()

            if counts[key] == 33:
                safe_reply_silent_fail(event.reply_token, f"تم اكتمال {key}")

                if all(counts[k] >= 33 for k in ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]):
                    congratulation_msg = "تم اكتمال الاذكار الاربعه\nجزاك الله خيرا"
                    safe_send_message(user_id, congratulation_msg)
                return

            status = get_tasbih_status(user_id, gid)
            safe_reply_silent_fail(event.reply_token, status)
            return

        # ================= أمر ذكرني =================
        if text_lower == "ذكرني":
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if not messages:
                return

            message = random.choice(messages)

            # الرد على من كتب الأمر
            safe_reply_silent_fail(event.reply_token, message)

            # إرسال نفس الذكر لجميع المستخدمين والمجموعات
            for uid in list(target_users):
                safe_send_message(uid, message)

            for g in list(target_groups):
                safe_send_message(g, message)
            return

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)

# ================= Webhook =================
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
        logger.warning("توقيع غير صالح")
    except Exception as e:
        logger.error(f"خطأ في معالجة Webhook: {e}")
    return "OK", 200

# ================= تشغيل التطبيق =================
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
