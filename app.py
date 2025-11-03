from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time, logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from functools import wraps
from collections import defaultdict

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
MORNING_ADHKAR_FILE = "morning_adhkar.json"
EVENING_ADHKAR_FILE = "evening_adhkar.json"
SLEEP_ADHKAR_FILE = "sleep_adhkar.json"

# ================= Locks للحماية من Race Conditions =================
data_lock = threading.Lock()
fadl_lock = threading.Lock()

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
    with fadl_lock:  # حماية من race conditions
        if not fadl_content:
            return "لا يوجد فضل متاح"
        message = fadl_content[fadl_index]
        fadl_index = (fadl_index + 1) % len(fadl_content)
        return message

# ================= تحميل أذكار الصباح والمساء والنوم =================
def load_adhkar_file(filename):
    try:
        if not os.path.exists(filename):
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({"adhkar": []}, f, ensure_ascii=False, indent=2)
            logger.info(f"{filename} تم إنشاؤه")
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("adhkar", [])
    except Exception as e:
        logger.error(f"خطأ في تحميل {filename}: {e}")
        return []

morning_adhkar = load_adhkar_file(MORNING_ADHKAR_FILE)
evening_adhkar = load_adhkar_file(EVENING_ADHKAR_FILE)
sleep_adhkar = load_adhkar_file(SLEEP_ADHKAR_FILE)

def get_adhkar_message(adhkar_list, title, emoji):
    """دالة موحدة لإنشاء رسائل الأذكار"""
    if not adhkar_list:
        return f"{emoji} {title}\n\nلا يوجد أذكار محفوظة"
    
    message = f"{emoji} {title}\n\n"
    message += "\n\n".join(adhkar_list)
    return message.strip()

def get_morning_adhkar_message():
    return get_adhkar_message(morning_adhkar, "أذكار الصباح", "🌅")

def get_evening_adhkar_message():
    return get_adhkar_message(evening_adhkar, "أذكار المساء", "🌆")

def get_sleep_adhkar_message():
    return get_adhkar_message(sleep_adhkar, "أذكار النوم", "🌙")

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
    """حفظ البيانات مع حماية من race conditions"""
    try:
        with data_lock:
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
def retry_on_failure(max_retries=3, delay=1):
    """Decorator لإعادة المحاولة عند الفشل"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"محاولة {attempt + 1} فشلت: {e}")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=2)
def safe_send_message(target_id, message):
    try:
        line_bot_api.push_message(target_id, TextSendMessage(text=message))
        return True
    except LineBotApiError as e:
        logger.error(f"فشل إرسال الرسالة إلى {target_id}: {e}")
        return False

def safe_reply(reply_token, message):
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=message))
        return True
    except Exception as e:
        logger.error(f"فشل الرد: {e}")
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

# خريطة التطبيع المحسّنة
TASBIH_NORMALIZE_MAP = {
    "استغفر الله": ["استغفرالله", "استغفراللة", "استغفراللله"],
    "سبحان الله": ["سبحانالله", "سبحاناللة", "سبحاناللله"],
    "الحمد لله": ["الحمدلله", "الحمدللة", "الحمدلللة"],
    "الله أكبر": ["اللهأكبر", "اللهاكبر", "اللةأكبر", "اللةاكبر", "اللللهاكبر"]
}

# إنشاء خريطة عكسية للبحث السريع
REVERSE_TASBIH_MAP = {}
for standard, variants in TASBIH_NORMALIZE_MAP.items():
    for variant in variants:
        REVERSE_TASBIH_MAP[variant] = standard

def normalize_tasbih_text(text):
    """تطبيع نص التسبيح - نسخة محسّنة"""
    # إزالة المسافات وتطبيع الأحرف
    normalized = text.replace(" ", "").replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("ة", "ه")
    
    # البحث في الخريطة العكسية
    return REVERSE_TASBIH_MAP.get(normalized, None)

def ensure_user_counts(uid):
    """التأكد من وجود عداد للمستخدم - مع حماية"""
    with data_lock:
        if uid not in tasbih_counts:
            tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
            save_data()

def get_tasbih_status(user_id, gid=None):
    """عرض حالة التسبيح"""
    with data_lock:
        counts = tasbih_counts.get(user_id, {key: 0 for key in TASBIH_KEYS})
    
    display_name = get_group_member_display_name(gid, user_id) if gid else get_user_display_name(user_id)
    
    status_lines = [f"حالة التسبيح\n{display_name}\n"]
    for key in TASBIH_KEYS:
        status_lines.append(f"{key}: {counts.get(key, 0)}/33")
    
    return "\n".join(status_lines)

# ================= إرسال أذكار الصباح والمساء والنوم =================
def send_adhkar_to_all(message, adhkar_type):
    """دالة موحدة لإرسال الأذكار"""
    sent_count = 0
    
    for uid in list(target_users):
        if safe_send_message(uid, message):
            sent_count += 1
    
    for gid in list(target_groups):
        if safe_send_message(gid, message):
            sent_count += 1
    
    logger.info(f"تم إرسال {adhkar_type} إلى {sent_count} مستخدم/مجموعة")

def send_morning_adhkar():
    send_adhkar_to_all(get_morning_adhkar_message(), "أذكار الصباح")

def send_evening_adhkar():
    send_adhkar_to_all(get_evening_adhkar_message(), "أذكار المساء")

def send_sleep_adhkar():
    send_adhkar_to_all(get_sleep_adhkar_message(), "أذكار النوم")

# ================= جدولة أذكار محسّنة =================
def adhkar_scheduler():
    """جدولة أذكار الصباح والمساء والنوم - نسخة محسّنة"""
    sa_timezone = pytz.timezone("Asia/Riyadh")
    sent_today = {"morning": None, "evening": None, "sleep": None}
    
    schedules = [
        ("06:00", "morning", send_morning_adhkar),
        ("17:00", "evening", send_evening_adhkar),
        ("22:00", "sleep", send_sleep_adhkar)
    ]
    
    while True:
        try:
            now = datetime.now(sa_timezone)
            current_time = now.strftime("%H:%M")
            today_date = now.date()
            
            for scheduled_time, key, send_func in schedules:
                if current_time == scheduled_time and sent_today[key] != today_date:
                    send_func()
                    sent_today[key] = today_date
            
            # النوم لمدة 30 ثانية
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"خطأ في جدولة الأذكار: {e}")
            time.sleep(60)

threading.Thread(target=adhkar_scheduler, daemon=True).start()

# ================= حماية الروابط مع تنظيف =================
links_count = defaultdict(lambda: {"count": 0, "timestamp": None})
LINK_RESET_HOURS = 24

def cleanup_old_link_counts():
    """تنظيف عدادات الروابط القديمة"""
    while True:
        try:
            now = datetime.now()
            to_delete = []
            
            for user_id, data in links_count.items():
                if data["timestamp"] and (now - data["timestamp"]).total_seconds() > LINK_RESET_HOURS * 3600:
                    to_delete.append(user_id)
            
            for user_id in to_delete:
                del links_count[user_id]
            
            logger.info(f"تم تنظيف {len(to_delete)} عداد روابط قديم")
            
        except Exception as e:
            logger.error(f"خطأ في تنظيف الروابط: {e}")
        
        time.sleep(3600)  # كل ساعة

threading.Thread(target=cleanup_old_link_counts, daemon=True).start()

def handle_links(event, user_id, gid=None):
    try:
        text = event.message.text.strip()
        if any(x in text.lower() for x in ["http://", "https://", "www."]):
            user_data = links_count[user_id]
            
            if user_data["timestamp"] is None:
                user_data["timestamp"] = datetime.now()
            
            user_data["count"] += 1

            if user_data["count"] == 2:
                display_name = get_group_member_display_name(gid, user_id) if gid else get_user_display_name(user_id)
                warning = f"{display_name}\nالرجاء عدم تكرار إرسال الروابط"
                safe_reply(event.reply_token, warning)
                logger.info(f"تحذير {user_id} من الروابط")
                return True

            elif user_data["count"] >= 3:
                logger.info(f"تجاهل رابط من {user_id}")
                return True

            return True
    except Exception as e:
        logger.error(f"خطأ في معالجة الروابط: {e}")
    return False

# ================= الرد على السلام =================
SALAM_KEYWORDS = {
    "السلام عليكم", "سلام عليكم", "السلام", "سلام",
    "عليكم السلام", "السلام عليكم ورحمة الله",
    "السلام عليكم ورحمة الله وبركاته", "سلام عليكم ورحمة الله",
    "سلامو عليكم", "سلامو", "سلامون عليكم", "سلامن"
}

def check_salam(text):
    text_lower = text.lower()
    return any(s in text_lower for s in SALAM_KEYWORDS)

# ================= قائمة الأوامر =================
VALID_COMMANDS = {
    "مساعدة", "فضل", "تسبيح",
    "استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر",
    "ذكرني"
}

def is_valid_command(text):
    """التحقق من أن النص هو أمر صالح"""
    text_lower = text.lower().strip()
    
    if check_salam(text):
        return True
    
    if text_lower in {cmd.lower() for cmd in VALID_COMMANDS}:
        return True
    
    if normalize_tasbih_text(text):
        return True
    
    return False

# ================= معالجة الرسائل =================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, "group_id", None)

        # تسجيل المستخدمين والمجموعات
        with data_lock:
            if user_id not in target_users:
                target_users.add(user_id)
                logger.info(f"مستخدم جديد: {user_id}")
                save_data()

            if gid and gid not in target_groups:
                target_groups.add(gid)
                logger.info(f"مجموعة جديدة: {gid}")
                save_data()

        ensure_user_counts(user_id)

        # حماية الروابط
        if handle_links(event, user_id, gid):
            return

        # تجاهل الرسائل غير المعترف بها
        if not is_valid_command(user_text):
            logger.info(f"تجاهل رسالة من {user_id}: {user_text[:50]}")
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
            except FileNotFoundError:
                safe_reply(event.reply_token, "ملف المساعدة غير متوفر حاليًا")
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

        # معالجة التسبيح
        normalized = normalize_tasbih_text(user_text)
        if normalized:
            with data_lock:
                counts = tasbih_counts[user_id]
                
                if counts[normalized] >= TASBIH_LIMITS:
                    safe_reply(event.reply_token, f"تم اكتمال {normalized} مسبقًا")
                    return
                
                counts[normalized] += 1
                save_data()
                
                current_count = counts[normalized]

            # رسالة اكتمال الذكر
            if current_count == TASBIH_LIMITS:
                safe_reply(event.reply_token, f"تم اكتمال {normalized}")
                
                # التحقق من اكتمال جميع الأذكار
                with data_lock:
                    all_complete = all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS)
                
                if all_complete:
                    safe_send_message(user_id, "تم اكتمال التسبيحات الأربعة، جزاك الله خيرًا")
                return
            
            # عرض الحالة
            status = get_tasbih_status(user_id, gid)
            safe_reply(event.reply_token, status)
            return

        # أمر ذكرني
        if text_lower == "ذكرني":
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if not messages:
                safe_reply(event.reply_token, "لا يوجد محتوى متاح حاليًا")
                return
            
            message = random.choice(messages)
            safe_reply(event.reply_token, message)
            
            # الإرسال لجميع المستخدمين والمجموعات الأخرى
            for uid in list(target_users):
                if uid != user_id:
                    safe_send_message(uid, message)
            
            for g in list(target_groups):
                if g != gid:
                    safe_send_message(g, message)
            
            return

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)

# ================= Webhook =================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "message": "Bot is active"}), 200

@app.route("/health", methods=["GET"])
def health_check():
    """نقطة فحص صحة البوت"""
    with data_lock:
        users_count = len(target_users)
        groups_count = len(target_groups)
    
    return jsonify({
        "status": "healthy",
        "users": users_count,
        "groups": groups_count,
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("توقيع غير صالح")
        return "Invalid signature", 400
    except Exception as e:
        logger.error(f"خطأ في Webhook: {e}")
    return "OK", 200

# ================= تذكير يدوي عبر كرون =================
@app.route("/reminder", methods=["GET"])
def reminder():
    """إرسال ذكر عشوائي لجميع المستخدمين والمجموعات"""
    try:
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if not messages:
            logger.warning("لا يوجد محتوى متاح للإرسال")
            return jsonify({"status": "no_content"}), 200

        message = random.choice(messages)
        sent_count = 0

        for uid in list(target_users):
            if safe_send_message(uid, message):
                sent_count += 1

        for gid in list(target_groups):
            if safe_send_message(gid, message):
                sent_count += 1

        logger.info(f"📤 تم إرسال تذكير عشوائي إلى {sent_count} مستخدم/مجموعة")
        return jsonify({
            "status": "ok",
            "sent": sent_count,
            "category": category
        }), 200

    except Exception as e:
        logger.error(f"خطأ في /reminder: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# ================= تشغيل التطبيق =================
if __name__ == "__main__":
    with data_lock:
        users_count = len(target_users)
        groups_count = len(target_groups)
    
    logger.info(f"🚀 تشغيل البوت على المنفذ {PORT}")
    logger.info(f"👥 عدد المستخدمين: {users_count}")
    logger.info(f"👨‍👩‍👧‍👦 عدد المجموعات: {groups_count}")
    
    app.run(host="0.0.0.0", port=PORT, threaded=True)
