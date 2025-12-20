from flask import Flask, request, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
import os, random, json, threading, time, logging
from datetime import datetime
import pytz

# -------------------------------
# Logging & Flask
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Bot85")

app = Flask(__name__)

# -------------------------------
# Configuration
# -------------------------------
ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

if not ACCESS_TOKEN or not SECRET:
    logger.error("مفاتيح LINE غير موجودة")
    raise ValueError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

DATA_FILE = "data/data.json"
CONTENT_DIR = "data"

TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]
TASBIH_LIMITS = 33

# -------------------------------
# Helper Functions
# -------------------------------
def load_json(file, default):
    if not os.path.exists(file):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ تحميل {file}: {e}")
        return default

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "groups": list(target_groups),
                "tasbih": tasbih_counts,
                "recent_reminders": recent_reminders
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ حفظ البيانات: {e}")

def load_content(file_name, key):
    path = os.path.join(CONTENT_DIR, file_name)
    return load_json(path, {key: []}).get(key, [])

def send_message(target_id, message):
    def async_send():
        try:
            with ApiClient(configuration) as api_client:
                api = MessagingApi(api_client)
                if isinstance(message, str):
                    api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=message)]))
                else:
                    api.push_message(PushMessageRequest(to=target_id, messages=[message]))
        except Exception as e:
            logger.error(f"ارسال رسالة فشل لـ {target_id}: {e}")
    threading.Thread(target=async_send, daemon=True).start()

def reply_message(reply_token, message):
    def async_reply():
        try:
            with ApiClient(configuration) as api_client:
                api = MessagingApi(api_client)
                if isinstance(message, str):
                    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)]))
                else:
                    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]))
        except Exception as e:
            logger.error(f"رد فشل: {e}")
    threading.Thread(target=async_reply, daemon=True).start()

def broadcast_text(text):
    sent, failed = 0, 0
    for gid in list(target_groups):
        try:
            send_message(gid, text)
            sent += 1
            time.sleep(0.05)
        except:
            failed += 1
    logger.info(f"Broadcast: {sent} نجح، {failed} فشل")
    return sent, failed

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        save_data()

# -------------------------------
# Load Data
# -------------------------------
data = load_json(DATA_FILE, {"groups": [], "tasbih": {}, "recent_reminders": {}})
target_groups = set(data.get("groups", []))
tasbih_counts = data.get("tasbih", {})
recent_reminders = data.get("recent_reminders", {})

# تحميل المحتوى
content = load_content("content.json", "duas")
fadl_content = load_content("fadl.json", "fadl")
morning_adhkar = load_content("morning_adhkar.json", "adhkar")
evening_adhkar = load_content("evening_adhkar.json", "adhkar")
sleep_adhkar = load_content("sleep_adhkar.json", "adhkar")

fadl_index = 0

# -------------------------------
# Tasbih Flex Builder
# -------------------------------
def create_tasbih_flex(user_id):
    counts = tasbih_counts.get(user_id, {key:0 for key in TASBIH_KEYS})
    total = sum(counts.values())
    total_max = TASBIH_LIMITS * len(TASBIH_KEYS)
    percentage = int((total / total_max) * 100)

    def create_row(text):
        count = counts.get(text, 0)
        completed = count >= TASBIH_LIMITS
        return {
            "type":"box","layout":"horizontal",
            "contents":[
                {"type":"text","text":text,"size":"sm","weight":"bold",
                 "color":"#ffffff" if not completed else "#00ff00","flex":2},
                {"type":"text","text":f"{count}/33","size":"sm",
                 "color":"#c0c0c0" if not completed else "#00ff00","align":"end","flex":1}
            ],
            "paddingAll":"8px",
            "backgroundColor":"#2a2a2a" if not completed else "#1a3f1a",
            "cornerRadius":"5px",
            "margin":"xs"
        }

    def create_button(text):
        return {
            "type":"button",
            "action":{"type":"postback","label":text,"data":f"tasbih_{text}_{user_id}"},
            "style":"secondary",
            "color":"#404040",
            "height":"sm"
        }

    progress_bar = {
        "type":"box","layout":"vertical","contents":[
            {"type":"text","text":f"التقدم: {percentage}%", "size":"xs","color":"#c0c0c0","align":"center"},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"box","layout":"baseline","contents":[],"flex":percentage,"backgroundColor":"#00ff00","height":"6px"},
                {"type":"box","layout":"baseline","contents":[],"flex":100-percentage,"backgroundColor":"#404040","height":"6px"}
            ], "cornerRadius":"3px","margin":"xs"}
        ],
        "margin":"md"
    }

    flex_content = {
        "type":"bubble","size":"kilo",
        "body":{
            "type":"box","layout":"vertical","paddingAll":"12px","backgroundColor":"#0a0a0a",
            "contents":[
                {"type":"text","text":"بوت 85","size":"md","weight":"bold","color":"#ffffff","align":"center"},
                progress_bar,
                {"type":"box","layout":"vertical","contents":[create_row(k) for k in TASBIH_KEYS],"margin":"md"},
                {"type":"box","layout":"horizontal","contents":[create_button(k) for k in TASBIH_KEYS[:2]],"spacing":"xs","margin":"md"},
                {"type":"box","layout":"horizontal","contents":[create_button(k) for k in TASBIH_KEYS[2:]],"spacing":"xs","margin":"xs"},
                {"type":"separator","margin":"md","color":"#303030"},
                {"type":"text","text":"تم إنشاء هذا البوت بواسطة عبير الدوسري @2025",
                 "size":"xxs","color":"#606060","align":"center","margin":"sm"}
            ]
        }
    }
    return FlexMessage(alt_text="التسبيح", contents=FlexContainer.from_dict(flex_content))

# -------------------------------
# Adhkar Scheduler
# -------------------------------
def adhkar_scheduler():
    sa_tz = pytz.timezone("Asia/Riyadh")
    sent = {"morning": None, "evening": None, "sleep": None}
    while True:
        try:
            now = datetime.now(sa_tz)
            h, m = now.hour, now.minute
            today = now.date()
            if h==6 and m==0 and sent["morning"]!=today:
                broadcast_text(get_adhkar_message(morning_adhkar,"أذكار الصباح"))
                sent["morning"]=today
            if h==17 and m==0 and sent["evening"]!=today:
                broadcast_text(get_adhkar_message(evening_adhkar,"أذكار المساء"))
                sent["evening"]=today
            if h==22 and m==0 and sent["sleep"]!=today:
                broadcast_text(get_adhkar_message(sleep_adhkar,"أذكار النوم"))
                sent["sleep"]=today
            time.sleep(50)
        except Exception as e:
            logger.error(f"خطأ جدولة: {e}")
            time.sleep(60)

def get_adhkar_message(adhkar_list, title):
    if not adhkar_list: return f"{title}\n\nلا يوجد أذكار"
    return title + "\n\n" + "\n\n".join(adhkar_list[:5])

# -------------------------------
# Message Handlers
# -------------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source,"group_id",None)

        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()
        ensure_user_counts(user_id)

        text_lower = text.lower()
        # أوامر
        if text_lower=="مساعدة":
            reply_message(event.reply_token,"بوت 85\n\nتسبيح - نافذة التسبيح\nفضل - فضل العبادات\nذكرني - تذكير يدوي")
            return
        if text_lower=="فضل":
            global fadl_index
            msg = fadl_content[fadl_index] if fadl_content else "لا يوجد فضل متاح"
            fadl_index = (fadl_index+1)%len(fadl_content) if fadl_content else 0
            reply_message(event.reply_token,msg)
            return
        if text_lower=="تسبيح":
            reply_message(event.reply_token,create_tasbih_flex(user_id))
            return
        if text_lower=="ذكرني":
            category = random.choice(["duas","adhkar","hadiths","quran"])
            messages = load_content("content.json", category)
            recent = recent_reminders.get(user_id, [])
            choices = [m for m in messages if m not in recent]
            if not choices: choices = messages
            message = random.choice(choices) if choices else "لا يوجد محتوى"
            reply_message(event.reply_token,message)
            recent = [message]+recent[:4]
            recent_reminders[user_id]=recent
            save_data()
            return
        # رد السلام
        if any(s in text for s in ["السلام","سلام"]):
            reply_message(event.reply_token,"وعليكم السلام ورحمة الله وبركاته")
            return
    except Exception as e:
        logger.error(f"خطأ handle_message: {e}")

@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        data = event.postback.data
        if data.startswith("tasbih_"):
            parts = data.replace("tasbih_","").rsplit("_",1)
            if len(parts)!=2: return
            tasbih_text,user_id = parts
            ensure_user_counts(user_id)
            counts = tasbih_counts[user_id]
            if tasbih_text in TASBIH_KEYS and counts[tasbih_text]<TASBIH_LIMITS:
                counts[tasbih_text]+=1
                save_data()
                reply_message(event.reply_token,f"{tasbih_text} ({counts[tasbih_text]}/33)")
    except Exception as e:
        logger.error(f"خطأ handle_postback: {e}")

# -------------------------------
# Flask Routes
# -------------------------------
@app.route("/ping",methods=["GET"])
def ping(): return "pong",200

@app.route("/",methods=["GET"])
def home():
    return jsonify({"bot":"بوت 85","status":"نشط","endpoints":{"callback":"/callback","health":"/health","reminder":"/reminder"}}),200

@app.route("/health",methods=["GET"])
def health():
    return jsonify({
        "status":"ok",
        "groups":len(target_groups),
        "users":len(tasbih_counts),
        "scheduler_active":True,
        "recent_reminders":{k:len(v) for k,v in recent_reminders.items()}
    }),200

@app.route("/callback",methods=["GET","POST"])
def callback():
    if request.method=="GET":
        return jsonify({"status":"ok","endpoint":"callback"}),200
    signature = request.headers.get("X-Line-Signature","")
    body = request.get_data(as_text=True)
    if not signature: return "Missing signature",400
    def process_webhook():
        try: handler.handle(body,signature)
        except InvalidSignatureError: logger.error("Invalid signature")
        except Exception as e: logger.error(f"Webhook error: {e}")
    threading.Thread(target=process_webhook,daemon=True).start()
    return "OK",200

@app.route("/reminder",methods=["GET"])
def reminder():
    try:
        category = random.choice(["duas","adhkar","hadiths","quran"])
        messages = load_content("content.json", category)
        if messages: broadcast_text(random.choice(messages))
        return jsonify({"status":"ok"}),200
    except Exception as e:
        logger.error(f"Reminder error: {e}")
        return jsonify({"status":"error"}),500

# -------------------------------
# Start Scheduler
# -------------------------------
threading.Thread(target=adhkar_scheduler,daemon=True).start()
logger.info(f"بوت 85 يعمل على المنفذ {PORT}")
app.run(host="0.0.0.0",port=PORT)
