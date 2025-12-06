from flask import Flask, request, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os, random, json, threading, time, logging
from datetime import datetime
import pytz

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
    except:
        return default

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": list(target_users), "groups": list(target_groups), "tasbih": tasbih_counts}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ حفظ: {e}")

data = load_json(DATA_FILE, {"users": [], "groups": [], "tasbih": {}})
target_users = set(data.get("users", []))
target_groups = set(data.get("groups", []))
tasbih_counts = data.get("tasbih", {})

content = load_json(CONTENT_FILE, {"duas": [], "adhkar": [], "hadiths": [], "quran": []})
fadl_content = load_json("fadl.json", {"fadl": []}).get("fadl", [])
morning_adhkar = load_json("morning_adhkar.json", {"adhkar": []}).get("adhkar", [])
evening_adhkar = load_json("evening_adhkar.json", {"adhkar": []}).get("adhkar", [])
sleep_adhkar = load_json("sleep_adhkar.json", {"adhkar": []}).get("adhkar", [])

fadl_index = 0
TASBIH_LIMITS = 33
TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]

def get_next_fadl():
    global fadl_index
    if not fadl_content:
        return "لا يوجد فضل متاح"
    msg = fadl_content[fadl_index]
    fadl_index = (fadl_index + 1) % len(fadl_content)
    return msg

def get_adhkar_message(adhkar_list, title):
    if not adhkar_list:
        return f"{title}\n\nلا يوجد أذكار"
    msg = f"{title}\n\n"
    for a in adhkar_list:
        msg += f"{a}\n\n"
    return msg.strip()

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
    sent, failed = 0, 0
    for uid in list(target_users):
        if uid != exclude_user:
            if send_message(uid, text):
                sent += 1
            else:
                failed += 1
    for gid in list(target_groups):
        if gid != exclude_group:
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
        save_data()

def get_tasbih_status(user_id, gid=None):
    counts = tasbih_counts[user_id]
    name = get_group_member_name(gid, user_id) if gid else get_user_name(user_id)
    return f"حالة التسبيح\n{name}\n\nاستغفر الله: {counts['استغفر الله']}/33\nسبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"

def normalize_tasbih(text):
    text = text.replace(" ", "").replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("ة", "ه")
    m = {"استغفرالله": "استغفر الله", "سبحانالله": "سبحان الله", "الحمدلله": "الحمد لله", "اللهأكبر": "الله أكبر"}
    return m.get(text)

def adhkar_scheduler():
    sa_tz = pytz.timezone("Asia/Riyadh")
    sent = {"morning": None, "evening": None, "sleep": None}
    while True:
        try:
            now = datetime.now(sa_tz)
            h, m = now.hour, now.minute
            today = now.date()
            
            if h == 6 and m == 0 and sent["morning"] != today:
                broadcast_text(get_adhkar_message(morning_adhkar, "أذكار الصباح"))
                sent["morning"] = today
            elif h == 17 and m == 0 and sent["evening"] != today:
                broadcast_text(get_adhkar_message(evening_adhkar, "أذكار المساء"))
                sent["evening"] = today
            elif h == 22 and m == 0 and sent["sleep"] != today:
                broadcast_text(get_adhkar_message(sleep_adhkar, "أذكار النوم"))
                sent["sleep"] = today
            
            time.sleep(50)
        except Exception as e:
            logger.error(f"خطأ جدولة: {e}")
            time.sleep(60)

threading.Thread(target=adhkar_scheduler, daemon=True).start()

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
                return True
            return True
    except:
        pass
    return False

def check_salam(text):
    salam = ["السلام عليكم", "سلام عليكم", "السلام", "سلام", "عليكم السلام"]
    return any(s in text.lower() for s in salam)

VALID_COMMANDS = ["مساعدة", "فضل", "تسبيح", "استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر", "ذكرني"]

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
            help_text = "الأوامر:\n\n-ذكرني\nذكر/دعاء/حديث/آية\n\n-فضل\nفضل العبادات\n\n-تسبيح\nحالة التسبيح\n\nسبحان الله / الحمد لله / الله أكبر / استغفر الله\nزيادة العداد حتى 33"
            reply_message(event.reply_token, help_text)
            return

        if text_lower == "فضل":
            reply_message(event.reply_token, get_next_fadl())
            return

        if text_lower == "تسبيح":
            reply_message(event.reply_token, get_tasbih_status(user_id, gid))
            return

        normalized = normalize_tasbih(user_text)
        if normalized:
            counts = tasbih_counts[user_id]
            if counts[normalized] >= TASBIH_LIMITS:
                reply_message(event.reply_token, f"تم اكتمال {normalized} مسبقا")
                return
            
            counts[normalized] += 1
            save_data()

            if counts[normalized] == TASBIH_LIMITS:
                reply_message(event.reply_token, f"تم اكتمال {normalized}")
                if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                    send_message(user_id, "تم اكتمال التسبيحات الأربعة، جزاك الله خيراً")
                return
            
            reply_message(event.reply_token, get_tasbih_status(user_id, gid))
            return

        if text_lower == "ذكرني":
            try:
                category = random.choice(["duas", "adhkar", "hadiths", "quran"])
                messages = content.get(category, [])
                if not messages:
                    reply_message(event.reply_token, "لا يوجد محتوى")
                    return
                
                message = random.choice(messages)
                reply_message(event.reply_token, message)
                broadcast_text(message, exclude_user=user_id, exclude_group=gid)
            except Exception as e:
                logger.error(f"خطأ ذكرني: {e}")
            return

    except Exception as e:
        logger.error(f"خطأ معالجة: {e}")

def remind_all_on_start():
    try:
        time.sleep(10)
        logger.info("تشغيل ذكرني تلقائي...")
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if messages:
            broadcast_text(random.choice(messages))
    except Exception as e:
        logger.error(f"خطأ بدء تشغيل: {e}")

@app.route("/", methods=["GET"])
def home():
    return "Bot Active", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "users": len(target_users), "groups": len(target_groups)}), 200

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
        logger.error(f"خطأ webhook: {e}")
    return "OK", 200

@app.route("/reminder", methods=["GET"])
def reminder():
    try:
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if not messages:
            return jsonify({"status": "no_content"}), 200
        message = random.choice(messages)
        sent, failed = broadcast_text(message)
        return jsonify({"status": "ok", "sent": sent, "failed": failed}), 200
    except Exception as e:
        logger.error(f"خطأ reminder: {e}")
        return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    logger.info(f"بدء التشغيل - المنفذ {PORT}")
    logger.info(f"مستخدمين: {len(target_users)}, مجموعات: {len(target_groups)}")
    threading.Thread(target=remind_all_on_start, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
