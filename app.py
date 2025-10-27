from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time, logging
from dotenv import load_dotenv
import traceback

# ================= إعداد التسجيل =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= تحميل البيئة =================
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
except Exception as e:
    logger.error("خطأ في تهيئة LINE Bot:")
    traceback.print_exc()
    raise

# ================= ملفات البيانات =================
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"
FADL_FILE = "fadl.json"

# ================= إنشاء الملفات الناقصة تلقائي =================
def create_file_if_missing(path, default_content):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(default_content, dict):
                json.dump(default_content, f, ensure_ascii=False, indent=2)
            else:
                f.write(default_content)
        logger.info(f"{path} لم يكن موجودًا، تم إنشاؤه تلقائيًا")

create_file_if_missing(DATA_FILE, {"users": [], "groups": [], "tasbih": {}})
create_file_if_missing(FADL_FILE, {"fadl": ["لا إله إلا الله وحده لا شريك له"]})
create_file_if_missing(CONTENT_FILE, {"duas": ["دعاء مثال"], "adhkar": ["ذكر مثال"], "hadiths": ["حديث مثال"], "quran": ["آية مثال"]})
create_file_if_missing(HELP_FILE, "أوامر البوت:\n- فضل\n- تسبيح\n- ذكرني\n- مساعدة")

# ================= تحميل البيانات =================
def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل {path}: {e}")
        return {}

data = load_json(DATA_FILE)
target_users = set(data.get("users", []))
target_groups = set(data.get("groups", []))
tasbih_counts = data.get("tasbih", {})

fadl_content = load_json(FADL_FILE).get("fadl", [])
content = load_json(CONTENT_FILE)

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
    counts = tasbih_counts.get(user_id, {"استغفر الله": 0, "سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0})
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

        # تسجيل المستخدم/المجموعة تلقائي
        target_users.add(user_id)
        if gid:
            target_groups.add(gid)
        save_data()

        ensure_user_counts(user_id)

        # أوامر البوت
        if user_text == "تسبيح":
            msg = get_tasbih_status(user_id, gid)
            safe_reply_silent_fail(event.reply_token, msg)
        elif user_text == "فضل":
            fadl_msg = "\n".join(fadl_content)
            safe_reply_silent_fail(event.reply_token, fadl_msg)
        elif user_text == "ذكرني":
            send_random_message_to_all()
            safe_reply_silent_fail(event.reply_token, "تم إرسال ذكر عشوائي لجميع المستخدمين/المجموعات")
        elif user_text.lower() == "مساعدة":
            with open(HELP_FILE, "r", encoding="utf-8") as f:
                help_text = f.read()
            safe_reply_silent_fail(event.reply_token, help_text)
        elif handle_links(event, user_id, gid):
            pass
        else:
            safe_reply_silent_fail(event.reply_token, "الأمر غير معروف. اكتب 'مساعدة' للاطلاع على الأوامر.")
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        traceback.print_exc()

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
        traceback.print_exc()
    return "OK", 200

# ================= تشغيل التطبيق =================
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
