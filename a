from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
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

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ================= ملفات البيانات =================
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"
FADL_FILE = "fadl.json"

# ================= تحميل بيانات فضل =================
def load_fadl_content():
    try:
        if not os.path.exists(FADL_FILE):
            with open(FADL_FILE, "w", encoding="utf-8") as f:
                json.dump({"fadl": []}, f, ensure_ascii=False, indent=2)
            logger.info(f"{FADL_FILE} تم إنشاؤه")
        with open(FADL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("fadl", [])
    except Exception as e:
        logger.error(f"خطأ في تحميل {FADL_FILE}: {e}")
        return []

fadl_content = load_fadl_content()
fadl_index = 0

def get_next_fadl():
    global fadl_index
    if not fadl_content:
        return "لا يوجد فضل متاح"
    message = fadl_content[fadl_index]
    fadl_index = (fadl_index + 1) % len(fadl_content)
    return message

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

def safe_reply(reply_token, message):
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

# ================= التسبيح =================
TASBIH_LIMITS = 33
TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
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

def normalize_tasbih_text(text):
    text = text.replace(" ", "").replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("ة", "ه")
    tasbih_map = {
        "استغفرالله": "استغفر الله",
        "سبحانالله": "سبحان الله",
        "الحمدلله": "الحمد لله",
        "اللهأكبر": "الله أكبر"
    }
    return tasbih_map.get(text)

# ================= إرسال رسائل تلقائية =================
def send_random_message_to_all():
    try:
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if not messages:
            logger.warning(f"لا يوجد محتوى في {category}")
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
            sleep_time = random.randint(14400, 18000)
            logger.info(f"الرسالة القادمة بعد {sleep_time//3600} ساعة")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"خطأ في الجدولة: {e}")
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
                warning = f"{display_name}\nالرجاء عدم تكرار إرسال الروابط"
                safe_reply(event.reply_token, warning)
                logger.info(f"تحذير {user_id} من الروابط")
                return True

            elif links_count[user_id] >= 3:
                logger.info(f"تجاهل رابط من {user_id}")
                return True

            return True
    except Exception as e:
        logger.error(f"خطأ في معالجة الروابط: {e}")
    return False

# ================= الرد على السلام =================
def check_salam(text):
    salam_list = [
        "السلام عليكم", "سلام عليكم", "السلام", "سلام",
        "عليكم السلام", "السلام عليكم ورحمة الله",
        "السلام عليكم ورحمة الله وبركاته", "سلام عليكم ورحمة الله",
        "سلامو عليكم", "سلامو", "سلامون عليكم", "سلامن"
    ]
    text_lower = text.lower()
    return any(s in text_lower for s in salam_list)

# ================= معالجة الرسائل =================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, "group_id", None)

        # تسجيل المستخدمين والمجموعات
        if user_id not in target_users:
            target_users.add(user_id)
            save_data()
            logger.info(f"مستخدم جديد: {user_id}")

        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()
            logger.info(f"مجموعة جديدة: {gid}")

        ensure_user_counts(user_id)

        # حماية الروابط
        if handle_links(event, user_id, gid):
            return

        text_lower = user_text.lower()

        # الرد على السلام
        if check_salam(user_text):
            safe_reply(event.reply_token, "وعليكم السلام ورحمة الله وبركاته")
            return

        # أمر مساعدة
        if text_lower == "مساعدة":
            try:
                with open(HELP_FILE, "r", encoding="utf-8") as f:
                    help_text = f.read()
                safe_reply(event.reply_token, help_text)
            except:
                logger.error("ملف المساعدة غير موجود")
            return

        # أمر فضل
        if text_lower == "فضل":
            message = get_next_fadl()
            safe_reply(event.reply_token, message)
            return

        # أمر تسبيح
        if text_lower == "تسبيح":
            status = get_tasbih_status(user_id, gid)
            safe_reply(event.reply_token, status)
            return

        # معالجة التسبيح بجميع الصيغ
        normalized = normalize_tasbih_text(user_text)
        if normalized:
            counts = tasbih_counts[user_id]
            if counts[normalized] >= TASBIH_LIMITS:
                safe_reply(event.reply_token, f"تم اكتمال {normalized} مسبقا")
                return

            counts[normalized] += 1
            save_data()

            if counts[normalized] == TASBIH_LIMITS:
                safe_reply(event.reply_token, f"تم اكتمال {normalized}")
                if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                    safe_send_message(user_id, "تم اكتمال الأذكار الأربعة، جزاك الله خيرًا")
                return

            status = get_tasbih_status(user_id, gid)
            safe_reply(event.reply_token, status)
            return

        # ================= أمر ذكرني =================
        if text_lower == "ذكرني":
            try:
                category = random.choice(["duas", "adhkar", "hadiths", "quran"])
                messages = content.get(category, [])
                if not messages:
                    safe_reply(event.reply_token, "لا يوجد محتوى متاح الآن")
                    return

                message = random.choice(messages)

                # الرد على المستخدم مباشرة
                safe_reply(event.reply_token, message)

                # الإرسال لجميع المستخدمين والمجموعات
                sent_count = 0
                for uid in list(target_users):
                    if uid != user_id and safe_send_message(uid, message):
                        sent_count += 1

                for g in list(target_groups):
                    if g != gid and safe_send_message(g, message):
                        sent_count += 1

                logger.info(f"تم إرسال ذكرني إلى {sent_count} مستخدم/مجموعة")

            except Exception as e:
                logger.error(f"خطأ في أمر ذكرني: {e}", exc_info=True)
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
        logger.error(f"خطأ في Webhook: {e}")
    return "OK", 200

# ================= تشغيل التطبيق =================
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
