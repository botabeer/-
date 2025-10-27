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

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0, "استغفر الله": 0}
        save_data()

def get_tasbih_status(user_id):
    counts = tasbih_counts[user_id]
    return (
        f"حالة التسبيح:\n"
        f"استغفر الله: {counts['استغفر الله']}/33\n"
        f"سبحان الله: {counts['سبحان الله']}/33\n"
        f"الحمد لله: {counts['الحمد لله']}/33\n"
        f"الله أكبر: {counts['الله أكبر']}/33"
    )

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
        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()

        ensure_user_counts(user_id)

        text_lower = user_text.lower()

        # أمر فضل
        if text_lower == "فضل" and fadl_content:
            safe_reply_silent_fail(event.reply_token, random.choice(fadl_content))
            return

        # أمر التسبيح
        key_map = {
            "سبحانالله": "سبحان الله",
            "الحمدلله": "الحمد لله",
            "اللهاكبر": "الله أكبر",
            "استغفرالله": "استغفر الله"
        }
        clean_text = user_text.replace(" ", "").replace("أ", "ا").replace("إ", "ا").replace("ٱ", "ا").replace("آ","ا")
        key = key_map.get(clean_text)
        if key:
            counts = tasbih_counts[user_id]
            if counts[key] < 33:
                counts[key] += 1
                save_data()
            safe_reply_silent_fail(event.reply_token, get_tasbih_status(user_id))
            return

        # أمر ذكرني
        if text_lower == "ذكرني":
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if messages:
                message = random.choice(messages)
                safe_reply_silent_fail(event.reply_token, message)
            return

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)

# ================= تشغيل التطبيق =================
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
    return "OK", 200

if __name__ == "__main__":
    logger.info(f"تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
