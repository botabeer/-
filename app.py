from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time, logging
from dotenv import load_dotenv

# ---------------- إعداد التسجيل ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        initial_data = {
            "users": [],
            "groups": [],
            "tasbih": {}
        }
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

# ---------------- تحميل المحتوى ---------------- #
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

# ---------------- دالة إرسال رسائل آمنة ---------------- #
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

def safe_reply_message(reply_token, message):
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=message))
        return True
    except LineBotApiError as e:
        logger.warning(f"فشل الرد على الرسالة: {e}")
        return False
    except Exception as e:
        logger.error(f"خطأ غير متوقع في الرد: {e}")
        return False

# ---------------- إرسال ذكر/دعاء تلقائي ---------------- #
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
        logger.error(f": {e}")

def scheduled_messages():
    while True:
        try:
            send_random_message_to_all()
            sleep_time = random.randint(14400, 18000)
            logger.info(f"الرسالة التلقائية القادمة بعد {sleep_time//3600} ساعة")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f": {e}")
            time.sleep(3600)

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
        logger.warning("")
    except Exception as e:
        logger.error(f" Webhook: {e}")
    return "OK", 200

# ---------------- حماية الروابط ---------------- #
links_count = {}
def handle_links(event, user_id):
    try:
        text = event.message.text.strip()
        gid = getattr(event.source, 'group_id', None)
        
        if any(x in text.lower() for x in ["http://", "https://", "www."]):
            links_count[user_id] = links_count.get(user_id, 0) + 1
            
            if links_count[user_id] == 2:
                safe_reply_message(
                    event.reply_token,
                    "الرجاء عدم تكرار إرسال الروابط"
                )
                logger.info(f"تحذير المستخدم {user_id} من تكرار الروابط")
                return True
            
            elif links_count[user_id] >= 3 and gid:
                try:
                    line_bot_api.leave_group(gid)
                    logger.info(f"تم طرد المستخدم {user_id} من المجموعة {gid}")
                except Exception as e:
                    logger.error(f": {e}")
                return True
                
            return True
    except Exception as e:
        logger.error(f": {e}")
    return False

# ---------------- تسبيح ---------------- #
TASBIH_LIMITS = 33
TASBIH_KEYS = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله"]

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        save_data()

def get_tasbih_status(user_id):
    counts = tasbih_counts[user_id]
    status = "حالة التسبيح\n\n"
    status += f"سبحان الله: {counts['سبحان الله']}/33\n"
    status += f"الحمد لله: {counts['الحمد لله']}/33\n"
    status += f"الله أكبر: {counts['الله أكبر']}/33\n"
    status += f"استغفر الله: {counts['استغفر الله']}/33"
    return status

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, 'group_id', None)

        # تسجيل المستخدمين والمجموعات تلقائياً
        if user_id not in target_users:
            target_users.add(user_id)
            logger.info(f"مستخدم جديد: {user_id}")

        if gid and gid not in target_groups:
            target_groups.add(gid)
            logger.info(f"مجموعة جديدة: {gid}")

        save_data()
        ensure_user_counts(user_id)

        # حماية الروابط
        if handle_links(event, user_id):
            return

        user_text_lower = user_text.lower()

        # ---------------- أمر المساعدة ---------------- #
        if user_text_lower == "مساعدة":
            help_text = """دليل استخدام البوت

الاوامر المتاحة

تسبيح
عرض حالة التسبيح الحالية وعدد المرات المتبقية لكل ذكر

سبحان الله
ذكر التسبيح، يزيد العداد حتى يصل الى 33 مرة

الحمد لله
ذكر الحمد، يزيد العداد حتى يصل الى 33 مرة

الله أكبر
ذكر التكبير، يزيد العداد حتى يصل الى 33 مرة

استغفر الله
ذكر الاستغفار، يزيد العداد حتى يصل الى 33 مرة

ذكرني
الحصول على ذكر او دعاء او حديث او آية بشكل فوري
            
            safe_reply_message(event.reply_token, help_text)
            return

        # ---------------- عرض التسبيح ---------------- #
        if user_text_lower == "تسبيح":
            status = get_tasbih_status(user_id)
            safe_reply_message(event.reply_token, status)
            return

        # ---------------- التسبيح ---------------- #
        clean_text = user_text.replace(" ", "")
        key_map = {
            "سبحانالله": "سبحان الله",
            "الحمدلله": "الحمد لله",
            "اللهأكبر": "الله أكبر",
            "استغفرالله": "استغفر الله"
        }
        key = key_map.get(clean_text)
        
        if key:
            counts = tasbih_counts[user_id]
            
            # التحقق إذا الذكر وصل الحد الأقصى
            if counts[key] >= TASBIH_LIMITS:
                safe_reply_message(
                    event.reply_token,
                    f"تم اكتمال {key} مسبقا"
                )
                return
            
            counts[key] += 1
            save_data()

            # إشعار اكتمال ذكر واحد فقط
            if counts[key] == TASBIH_LIMITS:
                safe_reply_message(
                    event.reply_token,
                    f"تم اكتمال {key}"
                )
                
                # التحقق من اكتمال جميع الأذكار
                if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                    congratulation_msg = "تم اكتمال جميع الاذكار\n\nجزاك الله خير\nوجعل الله لك ولوالديك الجنة"
                    safe_send_message(user_id, congratulation_msg)
                return
            
            # عرض الحالة الحالية
            status = get_tasbih_status(user_id)
            safe_reply_message(event.reply_token, status)
            return

        # ---------------- أمر ذكرني ---------------- #
        if user_text_lower == "ذكرني":
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            
            if not messages:
                return
            
            message = random.choice(messages)
            
            # إرسال للمستخدم الذي طلب الأمر
            safe_reply_message(event.reply_token, message)
            
            # إرسال لجميع المستخدمين والمجموعات
            for uid in list(target_users):
                if uid != user_id:
                    safe_send_message(uid, message)
            
            for g in list(target_groups):
                if g != gid:
                    safe_send_message(g, message)
            
            return

        # تجاهل باقي الأوامر غير المعروفة
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)

# ---------------- تشغيل التطبيق ---------------- #
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
