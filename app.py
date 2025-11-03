from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, threading, time, logging
from dotenv import load_dotenv
from datetime import datetime
import pytz

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
# مفتاح سري للحماية من الوصول غير المصرح
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY", "your-secret-key-here")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ================= ملفات البيانات =================
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
HELP_FILE = "help.txt"
FADL_FILE = "fadl.json"
SCHEDULER_STATE_FILE = "scheduler_state.json"

# ================= تحميل وحفظ حالة الجدولة =================
def load_scheduler_state():
    """تحميل آخر وقت إرسال للرسائل التلقائية"""
    try:
        if not os.path.exists(SCHEDULER_STATE_FILE):
            return {"last_auto_send": None, "last_prayer_checks": {}}
        with open(SCHEDULER_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل حالة الجدولة: {e}")
        return {"last_auto_send": None, "last_prayer_checks": {}}

def save_scheduler_state(state):
    """حفظ حالة الجدولة"""
    try:
        with open(SCHEDULER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ حالة الجدولة: {e}")

scheduler_state = load_scheduler_state()

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
    except Exception as e:
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
    """تطبيع نص التسبيح لقبول جميع الصيغ"""
    text = text.replace(" ", "").replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("ة", "ه")
    
    tasbih_map = {
        "استغفرالله": "استغفر الله",
        "استغفراللة": "استغفر الله",
        "استغفراللله": "استغفر الله",
        "سبحانالله": "سبحان الله",
        "سبحاناللة": "سبحان الله",
        "سبحاناللله": "سبحان الله",
        "الحمدلله": "الحمد لله",
        "الحمدللة": "الحمد لله",
        "الحمدلللة": "الحمد لله",
        "اللهأكبر": "الله أكبر",
        "اللهاكبر": "الله أكبر",
        "اللةأكبر": "الله أكبر",
        "اللةاكبر": "الله أكبر",
        "اللللهاكبر": "الله أكبر"
    }
    
    return tasbih_map.get(text)

# ================= إرسال رسائل تلقائية محسّنة =================
def send_random_message_to_all():
    """إرسال رسالة عشوائية لجميع المستخدمين والمجموعات"""
    try:
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if not messages:
            logger.warning(f"لا يوجد محتوى في {category}")
            return False

        message = random.choice(messages)
        sent_count = 0
        failed_users = []
        failed_groups = []

        # إرسال للمستخدمين
        for uid in list(target_users):
            if safe_send_message(uid, message):
                sent_count += 1
            else:
                failed_users.append(uid)

        # إرسال للمجموعات
        for gid in list(target_groups):
            if safe_send_message(gid, message):
                sent_count += 1
            else:
                failed_groups.append(gid)

        # إزالة المستخدمين والمجموعات الفاشلة
        for uid in failed_users:
            target_users.discard(uid)
        for gid in failed_groups:
            target_groups.discard(gid)
        
        if failed_users or failed_groups:
            save_data()

        logger.info(f"تم إرسال رسالة تلقائية إلى {sent_count} مستخدم/مجموعة")
        
        # حفظ وقت الإرسال
        scheduler_state["last_auto_send"] = datetime.now().isoformat()
        save_scheduler_state(scheduler_state)
        
        return True
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسائل التلقائية: {e}")
        return False

# ================= نقاط نهاية HTTP للتذكير الخارجي =================
@app.route("/trigger-reminder", methods=["POST"])
def trigger_reminder():
    """نقطة نهاية لتفعيل التذكير التلقائي من خدمات Cron خارجية"""
    try:
        # التحقق من المفتاح السري
        auth_key = request.headers.get("X-Auth-Key") or request.args.get("key")
        if auth_key != CRON_SECRET_KEY:
            logger.warning("محاولة وصول غير مصرح بها لـ trigger-reminder")
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        success = send_random_message_to_all()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "تم إرسال الرسالة التلقائية",
                "timestamp": datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "فشل في إرسال الرسالة"
            }), 500
            
    except Exception as e:
        logger.error(f"خطأ في trigger-reminder: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/trigger-prayer", methods=["POST"])
def trigger_prayer():
    """نقطة نهاية لتفعيل تذكير الصلاة من خدمات Cron خارجية"""
    try:
        # التحقق من المفتاح السري
        auth_key = request.headers.get("X-Auth-Key") or request.args.get("key")
        if auth_key != CRON_SECRET_KEY:
            logger.warning("محاولة وصول غير مصرح بها لـ trigger-prayer")
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        # الحصول على اسم الصلاة من الطلب
        prayer_name = request.json.get("prayer") if request.is_json else request.args.get("prayer")
        
        if not prayer_name:
            return jsonify({"status": "error", "message": "اسم الصلاة مطلوب"}), 400
        
        message = f"🕌 وقت {prayer_name} الآن. لا تنس الصلاة وذكر الله."
        sent_count = 0
        
        # إرسال لجميع المستخدمين
        for uid in list(target_users):
            if safe_send_message(uid, message):
                sent_count += 1
        
        # إرسال لجميع المجموعات
        for gid in list(target_groups):
            if safe_send_message(gid, message):
                sent_count += 1
        
        # حفظ وقت الإرسال
        if "last_prayer_checks" not in scheduler_state:
            scheduler_state["last_prayer_checks"] = {}
        scheduler_state["last_prayer_checks"][prayer_name] = datetime.now().isoformat()
        save_scheduler_state(scheduler_state)
        
        logger.info(f"تم إرسال تذكير {prayer_name} إلى {sent_count} مستخدم/مجموعة")
        
        return jsonify({
            "status": "success",
            "message": f"تم إرسال تذكير {prayer_name}",
            "sent_count": sent_count,
            "timestamp": datetime.now().isoformat()
        }), 200
            
    except Exception as e:
        logger.error(f"خطأ في trigger-prayer: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ================= الجدولة الداخلية الاحتياطية =================
def scheduled_messages():
    """جدولة داخلية احتياطية في حال فشل الخدمات الخارجية"""
    while True:
        try:
            send_random_message_to_all()
            sleep_time = random.randint(14400, 18000)  # 4-5 ساعات
            logger.info(f"الرسالة القادمة بعد {sleep_time//3600} ساعة")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"خطأ في الجدولة الداخلية: {e}")
            time.sleep(3600)

# تشغيل الجدولة الداخلية كـ backup
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
            
            # التحقق من الوصول للحد
            if counts[normalized] >= TASBIH_LIMITS:
                safe_reply(event.reply_token, f"تم اكتمال {normalized} مسبقا")
                return
            
            counts[normalized] += 1
            save_data()

            # رسالة اكتمال الذكر
            if counts[normalized] == TASBIH_LIMITS:
                safe_reply(event.reply_token, f"تم اكتمال {normalized}")
                
                # التحقق من اكتمال جميع الأذكار الأربعة
                if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                    safe_send_message(user_id, "تم اكتمال الأذكار الأربعة، جزاك الله خيرًا")
                return
            
            # عرض الحالة
            status = get_tasbih_status(user_id, gid)
            safe_reply(event.reply_token, status)
            return

        # أمر ذكرني اليدوي
        if text_lower == "ذكرني":
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if not messages:
                return
            
            message = random.choice(messages)
            
            # الرد للمستخدم
            safe_reply(event.reply_token, message)
            
            # الإرسال لجميع المستخدمين والمجموعات
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
    return "Bot is running", 200

@app.route("/health", methods=["GET"])
def health_check():
    """نقطة فحص صحة البوت"""
    return jsonify({
        "status": "healthy",
        "users": len(target_users),
        "groups": len(target_groups),
        "last_auto_send": scheduler_state.get("last_auto_send"),
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
    except Exception as e:
        logger.error(f"خطأ في Webhook: {e}")
    return "OK", 200

# ================= تذكير تلقائي بأوقات الصلاة (داخلي احتياطي) =================
PRAYER_TIMES = {
    "الفجر": "05:00",
    "الظهر": "12:30",
    "العصر": "15:45",
    "المغرب": "18:10",
    "العشاء": "19:30"
}

def prayer_time_reminder():
    """تذكير داخلي بأوقات الصلاة - احتياطي"""
    sa_timezone = pytz.timezone("Asia/Riyadh")
    sent_today = set()

    while True:
        try:
            now = datetime.now(sa_timezone)
            current_time = now.strftime("%H:%M")
            today_date = now.date()

            for prayer, prayer_time in PRAYER_TIMES.items():
                key = (today_date, prayer)
                if current_time == prayer_time and key not in sent_today:
                    message = f"🕌 وقت {prayer} الآن. لا تنس الصلاة وذكر الله."
                    
                    # إرسال لجميع المستخدمين
                    for uid in list(target_users):
                        safe_send_message(uid, message)
                    
                    # إرسال لجميع المجموعات
                    for gid in list(target_groups):
                        safe_send_message(gid, message)
                    
                    sent_today.add(key)
                    
                    # حفظ الحالة
                    if "last_prayer_checks" not in scheduler_state:
                        scheduler_state["last_prayer_checks"] = {}
                    scheduler_state["last_prayer_checks"][prayer] = now.isoformat()
                    save_scheduler_state(scheduler_state)
            
            # تنظيف sent_today عند بداية يوم جديد
            if len(sent_today) > 50:
                sent_today.clear()
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"خطأ في تذكير الصلاة: {e}")
            time.sleep(60)

threading.Thread(target=prayer_time_reminder, daemon=True).start()

# ================= تشغيل التطبيق =================
if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    logger.info(f"عدد المستخدمين: {len(target_users)}")
    logger.info(f"عدد المجموعات: {len(target_groups)}")
    app.run(host="0.0.0.0", port=PORT)
