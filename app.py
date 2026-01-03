from flask import Flask, request, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os, random, json, logging, threading, time
from datetime import datetime, date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

DATA_FILE = "data.json"
CONTENT_FILE = "content.json"

def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل {file}: {e}")
        return default

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "users": list(target_users),
                "groups": list(target_groups),
                "tasbih": tasbih_counts,
                "last_reset": last_reset_dates,
                "notifications_off": list(notifications_off)
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ حفظ: {e}")

data = load_json(DATA_FILE, {"users": [], "groups": [], "tasbih": {}, "last_reset": {}, "notifications_off": []})
target_users = set(data.get("users", []))
target_groups = set(data.get("groups", []))
tasbih_counts = data.get("tasbih", {})
last_reset_dates = data.get("last_reset", {})
notifications_off = set(data.get("notifications_off", []))

content = load_json(CONTENT_FILE, {"adhkar": []})
fadl_content = load_json("fadl.json", {"fadl": []}).get("fadl", [])

fadl_index = 0
TASBIH_LIMITS = 33
TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]

# إعدادات التذكير التلقائي
AUTO_REMINDER_ENABLED = True
MIN_INTERVAL_HOURS = 4
MAX_INTERVAL_HOURS = 6

def get_next_fadl():
    global fadl_index
    if not fadl_content:
        return "لا يوجد فضل متاح"
    msg = fadl_content[fadl_index]
    fadl_index = (fadl_index + 1) % len(fadl_content)
    return msg

def send_message(target_id, text):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=text)]))
        return True
    except Exception as e:
        if "400" not in str(e) and "403" not in str(e):
            logger.error(f"ارسال فشل {target_id}: {e}")
        return False

def reply_message(reply_token, text):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)]))
        return True
    except Exception as e:
        logger.error(f"رد فشل: {e}")
        return False

def broadcast_text(text, exclude_user=None, exclude_group=None):
    """إرسال لجميع المستخدمين والمجموعات (مع احترام إعدادات الإيقاف)"""
    sent, failed = 0, 0
    
    for uid in list(target_users):
        if uid != exclude_user and uid not in notifications_off:
            if send_message(uid, text):
                sent += 1
            else:
                failed += 1
    
    for gid in list(target_groups):
        if gid != exclude_group and gid not in notifications_off:
            if send_message(gid, text):
                sent += 1
            else:
                failed += 1
    
    logger.info(f"ارسال: {sent} نجح، {failed} فشل")
    return sent, failed

def get_user_name(user_id):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            profile = api.get_profile(user_id)
            return profile.display_name
    except:
        return "المستخدم"

def get_group_member_name(group_id, user_id):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            profile = api.get_group_member_profile(group_id, user_id)
            return profile.display_name
    except:
        return "المستخدم"

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        last_reset_dates[uid] = str(date.today())
        save_data()

def reset_tasbih_if_needed(user_id):
    today = str(date.today())
    last_reset = last_reset_dates.get(user_id)
    
    if last_reset != today:
        tasbih_counts[user_id] = {key: 0 for key in TASBIH_KEYS}
        last_reset_dates[user_id] = today
        save_data()
        return True
    return False

def get_tasbih_status(user_id, gid=None):
    counts = tasbih_counts[user_id]
    name = get_group_member_name(gid, user_id) if gid else get_user_name(user_id)
    status = f"حالة التسبيح\n{name}\n\n"
    
    for key in TASBIH_KEYS:
        count = counts[key]
        status += f"{key}: {count}/33\n"
    
    all_complete = all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS)
    if all_complete:
        status += "\nتم إكمال جميع الأذكار"
    
    return status

def normalize_tasbih(text):
    text = text.replace(" ", "").replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("ة", "ه")
    m = {
        "استغفرالله": "استغفر الله",
        "سبحانالله": "سبحان الله",
        "الحمدلله": "الحمد لله",
        "اللهأكبر": "الله أكبر"
    }
    return m.get(text)

def auto_reminder_service():
    """خدمة التذكير التلقائي"""
    logger.info("بدء خدمة التذكير التلقائي")
    
    while AUTO_REMINDER_ENABLED:
        try:
            sleep_hours = random.uniform(MIN_INTERVAL_HOURS, MAX_INTERVAL_HOURS)
            sleep_seconds = sleep_hours * 3600
            
            logger.info(f"التذكير القادم بعد {sleep_hours:.1f} ساعة")
            time.sleep(sleep_seconds)
            
            if len(target_users) > 0 or len(target_groups) > 0:
                adhkar_list = content.get("adhkar", [])
                
                if adhkar_list:
                    message = random.choice(adhkar_list)
                    sent, failed = broadcast_text(message)
                    logger.info(f"تذكير تلقائي: تم الارسال الى {sent} - فشل {failed}")
                else:
                    logger.warning("لا يوجد أذكار للتذكير")
            else:
                logger.info("لا يوجد مستخدمين مسجلين")
                
        except Exception as e:
            logger.error(f"خطأ في التذكير التلقائي: {e}")
            time.sleep(3600)

if AUTO_REMINDER_ENABLED:
    reminder_thread = threading.Thread(target=auto_reminder_service, daemon=True)
    reminder_thread.start()
    logger.info("تم تشغيل خدمة التذكير التلقائي")

links_count = {}

def handle_links(event, user_id, gid=None):
    try:
        text = event.message.text.strip()
        if any(x in text.lower() for x in ["http://", "https://", "www."]):
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] == 2:
                name = get_group_member_name(gid, user_id) if gid else get_user_name(user_id)
                reply_message(event.reply_token, f"{name}\nالرجاء عدم تكرار إرسال الروابط")
                return True
            elif links_count[user_id] >= 3:
                logger.info(f"تم تجاهل رابط من {user_id}")
                return True
            return True
    except:
        pass
    return False

def check_salam(text):
    salam = ["السلام عليكم", "سلام عليكم", "السلام", "سلام", "عليكم السلام"]
    return any(s in text.lower() for s in salam)

VALID_COMMANDS = ["مساعدة", "فضل", "تسبيح", "استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر", "ذكرني", "إعادة", "إيقاف", "تشغيل"]

def is_valid_command(text):
    txt = text.lower().strip()
    if check_salam(text) or txt in [c.lower() for c in VALID_COMMANDS] or normalize_tasbih(text):
        return True
    return False

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, "group_id", None)

        if user_id not in target_users:
            target_users.add(user_id)
            save_data()
            logger.info(f"مستخدم جديد: {user_id}")

        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()
            logger.info(f"مجموعة جديدة: {gid}")

        ensure_user_counts(user_id)
        was_reset = reset_tasbih_if_needed(user_id)

        if handle_links(event, user_id, gid):
            return

        if not is_valid_command(user_text):
            logger.info(f"تجاهل: {user_text[:30]}")
            return

        text_lower = user_text.lower()

        if check_salam(user_text):
            reply_message(event.reply_token, "وعليكم السلام ورحمة الله وبركاته")
            return

        if text_lower == "مساعدة":
            help_text = """الأوامر المتاحة:

ذكرني
ارسال ذكر لجميع المستخدمين والمجموعات

فضل
عرض فضل العبادات والأذكار

تسبيح
عرض حالة التسبيح الخاصة بك

إعادة
تصفير عداد التسبيح وبدء من جديد

إيقاف
إيقاف التذكير التلقائي

تشغيل
تشغيل التذكير التلقائي

التسبيح الإلكتروني:
اكتب أي من الأذكار التالية لزيادة العداد حتى 33 مرة:
- سبحان الله
- الحمد لله
- الله أكبر
- استغفر الله

ملاحظة: 
- يتم تصفير العداد تلقائيا كل يوم
- يتم ارسال تذكير تلقائي كل 4-6 ساعات"""
            reply_message(event.reply_token, help_text)
            return

        if text_lower == "إيقاف":
            target_id = gid if gid else user_id
            if target_id not in notifications_off:
                notifications_off.add(target_id)
                save_data()
                if gid:
                    reply_message(event.reply_token, "تم إيقاف التذكير التلقائي لهذه المجموعة")
                else:
                    reply_message(event.reply_token, "تم إيقاف التذكير التلقائي لك")
                logger.info(f"إيقاف التذكير: {target_id}")
            else:
                reply_message(event.reply_token, "التذكير موقف مسبقا")
            return

        if text_lower == "تشغيل":
            target_id = gid if gid else user_id
            if target_id in notifications_off:
                notifications_off.remove(target_id)
                save_data()
                if gid:
                    reply_message(event.reply_token, "تم تشغيل التذكير التلقائي لهذه المجموعة")
                else:
                    reply_message(event.reply_token, "تم تشغيل التذكير التلقائي لك")
                logger.info(f"تشغيل التذكير: {target_id}")
            else:
                reply_message(event.reply_token, "التذكير يعمل مسبقا")
            return

        if text_lower == "فضل":
            reply_message(event.reply_token, get_next_fadl())
            return

        if text_lower == "تسبيح":
            status = get_tasbih_status(user_id, gid)
            if was_reset:
                status = "تم تصفير العداد ليوم جديد\n\n" + status
            reply_message(event.reply_token, status)
            return

        if text_lower == "إعادة":
            tasbih_counts[user_id] = {key: 0 for key in TASBIH_KEYS}
            last_reset_dates[user_id] = str(date.today())
            save_data()
            reply_message(event.reply_token, "تم تصفير عداد التسبيح بنجاح\nيمكنك البدء من جديد")
            logger.info(f"تم تصفير التسبيح يدويا: {user_id}")
            return

        normalized = normalize_tasbih(user_text)
        if normalized:
            counts = tasbih_counts[user_id]
            if counts[normalized] >= TASBIH_LIMITS:
                reply_message(event.reply_token, f"تم اكتمال {normalized} مسبقا\nاستخدم أمر: إعادة\nلتصفير العداد")
                return
            
            counts[normalized] += 1
            save_data()

            if counts[normalized] == TASBIH_LIMITS:
                reply_message(event.reply_token, f"تم اكتمال {normalized}")
                
                if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                    send_message(user_id, "تم اكتمال جميع التسبيحات الأربعة\nجزاك الله خيرا")
                return
            
            reply_message(event.reply_token, get_tasbih_status(user_id, gid))
            return

        if text_lower == "ذكرني":
            try:
                adhkar_list = content.get("adhkar", [])
                
                if not adhkar_list:
                    reply_message(event.reply_token, "لا يوجد أذكار متاحة")
                    logger.warning("لا يوجد أذكار في content.json")
                    return
                
                message = random.choice(adhkar_list)
                
                logger.info(f"تم اختيار ذكر: {message[:50]}...")
                
                reply_message(event.reply_token, message)
                sent, failed = broadcast_text(message, exclude_user=user_id, exclude_group=gid)
                
                logger.info(f"تم تنفيذ أمر ذكرني من {user_id}")
                logger.info(f"تم الارسال الى: {sent} - فشل: {failed}")
                
            except Exception as e:
                logger.error(f"خطأ في أمر ذكرني: {e}", exc_info=True)
                reply_message(event.reply_token, "حدث خطأ، حاول مرة أخرى")
            return

    except Exception as e:
        logger.error(f"خطأ معالجة الرسالة: {e}", exc_info=True)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "bot": "Islamic Reminder Bot",
        "users": len(target_users),
        "groups": len(target_groups),
        "notifications_disabled": len(notifications_off)
    }), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "users": len(target_users),
        "groups": len(target_groups),
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
        logger.error(f"خطأ webhook: {e}", exc_info=True)
    return "OK", 200

@app.route("/stats", methods=["GET"])
def stats():
    total_tasbih = sum(sum(counts.values()) for counts in tasbih_counts.values())
    active_receivers = len(target_users) + len(target_groups) - len(notifications_off)
    return jsonify({
        "total_users": len(target_users),
        "total_groups": len(target_groups),
        "total_tasbih_count": total_tasbih,
        "active_users": len(tasbih_counts),
        "notifications_disabled": len(notifications_off),
        "active_receivers": active_receivers,
        "auto_reminder_enabled": AUTO_REMINDER_ENABLED,
        "reminder_interval": f"{MIN_INTERVAL_HOURS}-{MAX_INTERVAL_HOURS} hours"
    }), 200

@app.route("/test_reminder", methods=["GET"])
def test_reminder():
    try:
        adhkar_list = content.get("adhkar", [])
        if adhkar_list:
            message = random.choice(adhkar_list)
            sent, failed = broadcast_text(message)
            return jsonify({
                "status": "success",
                "message": message[:100],
                "sent": sent,
                "failed": failed,
                "disabled_count": len(notifications_off)
            }), 200
        else:
            return jsonify({"status": "error", "message": "no adhkar"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    logger.info("=" * 40)
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    logger.info(f"المستخدمين: {len(target_users)}")
    logger.info(f"المجموعات: {len(target_groups)}")
    logger.info(f"التذكير موقف لـ: {len(notifications_off)}")
    logger.info(f"محتوى الأذكار: {len(content.get('adhkar', []))}")
    logger.info(f"التذكير التلقائي: {'مفعل' if AUTO_REMINDER_ENABLED else 'معطل'}")
    logger.info(f"فترة التذكير: {MIN_INTERVAL_HOURS}-{MAX_INTERVAL_HOURS} ساعة")
    logger.info("=" * 40)
    app.run(host="0.0.0.0", port=PORT)
