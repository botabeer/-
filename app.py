from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time, logging
from dotenv import load_dotenv

# –––––––– إعداد التسجيل ––––––––
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# –––––––– إعداد البوت ––––––––
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# –––––––– ملفات البيانات ––––––––
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"
FADL_FILE = "fadl.json"

def load_fadl_content():
    """تحميل محتوى فضل العبادات"""
    try:
        with open(FADL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("fadl", [])
    except FileNotFoundError:
        logger.error(f"ملف {FADL_FILE} غير موجود")
        return []
    except Exception as e:
        logger.error(f"خطأ في تحميل {FADL_FILE}: {e}")
        return []

def load_data():
    if not os.path.exists(DATA_FILE):
        initial_data = {"users": [], "groups": [], "tasbih": {}}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
        return set(), set(), {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return (
                set(data.get("users", [])),
                set(data.get("groups", [])),
                data.get("tasbih", {})
            )
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

def load_content():
    try:
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"ملف المحتوى {CONTENT_FILE} غير موجود")
        return {"duas": [], "adhkar": [], "hadiths": [], "quran": []}
    except Exception as e:
        logger.error(f"خطأ في تحميل المحتوى: {e}")
        return {"duas": [], "adhkar": [], "hadiths": [], "quran": []}

content = load_content()

# –––––––– دوال إرسال رسائل ––––––––
def safe_send_message(target_id, message):
    try:
        line_bot_api.push_message(target_id, TextSendMessage(text=message))
        return True
    except LineBotApiError as e:
        logger.warning(f"فشل إرسال رسالة إلى {target_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"خطأ غير متوقع في إرسال رسالة: {e}")
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

def safe_reply_silent_fail(reply_token, message):
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=message))
        return True
    except:
        return False

# –––––––– إرسال رسائل تلقائية ––––––––
def send_random_message_to_all():
    try:
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if not messages:
            return
        message = random.choice(messages)
        for uid in list(target_users):
            safe_send_message(uid, message)
        for gid in list(target_groups):
            safe_send_message(gid, message)
        logger.info(f"تم إرسال رسالة تلقائية من نوع {category}")
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسائل التلقائية: {e}")

def scheduled_messages():
    while True:
        try:
            send_random_message_to_all()
            sleep_time = random.randint(14400, 18000)  # بين 4 و 5 ساعات
            logger.info(f"الرسالة التلقائية القادمة بعد {sleep_time//3600} ساعة")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"خطأ في جدولة الرسائل: {e}")
            time.sleep(3600)

threading.Thread(target=scheduled_messages, daemon=True).start()

# –––––––– Webhook ––––––––
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

# –––––––– حماية الروابط ––––––––
links_count = {}
def handle_links(event, user_id, gid=None):
    try:
        text = event.message.text.strip()
        if any(x in text.lower() for x in ["http://", "https://", "www."]):
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] == 2:
                display_name = get_group_member_display_name(gid, user_id) if gid else get_user_display_name(user_id)
                safe_reply_silent_fail(event.reply_token, f"{display_name}\nالرجاء عدم تكرار إرسال الروابط")
            return True
    except Exception as e:
        logger.error(f"خطأ في معالجة الروابط: {e}")
    return False

# –––––––– تسبيح ––––––––
TASBIH_LIMITS = 33
TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        save_data()

def get_tasbih_status(user_id, gid=None):
    counts = tasbih_counts.get(user_id, {key:0 for key in TASBIH_KEYS})
    display_name = get_group_member_display_name(gid, user_id) if gid else get_user_display_name(user_id)
    status = f"حالة التسبيح\n{display_name}\n\n"
    for key in TASBIH_KEYS:
        status += f"{key}: {counts[key]}/33\n"
    return status

# –––––––– معالجة الرسائل ––––––––
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, 'group_id', None)

        # تسجيل المستخدمين والمجموعات
        if user_id not in target_users:
            target_users.add(user_id)
            save_data()
        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()
        ensure_user_counts(user_id)

        # حماية الروابط
        if handle_links(event, user_id, gid):
            return

        user_text_lower = user_text.lower()

        # الرد على السلام
        salam_variations = ["السلام عليكم","سلام عليكم","السلام","سلام","عليكم السلام"]
        if any(g in user_text_lower for g in salam_variations):
            safe_reply_silent_fail(event.reply_token, "وعليكم السلام ورحمة الله وبركاته")
            return

        # أمر المساعدة
        if user_text_lower == "مساعدة":
            try:
                with open(HELP_FILE,"r",encoding="utf-8") as f:
                    help_text = f.read()
                safe_reply_silent_fail(event.reply_token, help_text)
            except:
                pass
            return

        # أمر فضل
        if user_text_lower == "فضل":
            if fadl_content:
                safe_reply_silent_fail(event.reply_token, random.choice(fadl_content))
            return

        # أمر التسبيح
        if user_text_lower == "تسبيح":
            status = get_tasbih_status(user_id, gid)
            safe_reply_silent_fail(event.reply_token, status)
            return

        # أمر ذكرني
        if user_text_lower == "ذكرني":
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if messages:
                msg = random.choice(messages)
                safe_reply_silent_fail(event.reply_token, msg)
                for uid in target_users:
                    if uid != user_id:
                        safe_send_message(uid, msg)
                for g in target_groups:
                    if g != gid:
                        safe_send_message(g, msg)
            return

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)

# –––––––– تشغيل التطبيق ––––––––
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
