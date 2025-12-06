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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

if not ACCESS_TOKEN or not SECRET:
    logger.error("مفاتيح LINE غير موجودة")
    raise ValueError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

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
        logger.error(f"خطأ تحميل {file}: {e}")
        return default

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "groups": list(target_groups), 
                "tasbih": tasbih_counts
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ حفظ: {e}")

data = load_json(DATA_FILE, {"groups": [], "tasbih": {}})
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
    for a in adhkar_list[:5]:
        msg += f"{a}\n\n"
    return msg.strip()

def send_message(target_id, message):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            if isinstance(message, str):
                api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=message)]))
            else:
                api.push_message(PushMessageRequest(to=target_id, messages=[message]))
        return True
    except Exception as e:
        error_str = str(e)
        if "400" not in error_str and "403" not in error_str and "404" not in error_str:
            logger.error(f"ارسال فشل {target_id}: {e}")
        return False

def reply_message(reply_token, message):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            if isinstance(message, str):
                api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)]))
            else:
                api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]))
        return True
    except Exception as e:
        logger.error(f"رد فشل: {e}")
        return False

def broadcast_text(text):
    sent, failed = 0, 0
    for gid in list(target_groups):
        if send_message(gid, text):
            sent += 1
            time.sleep(0.1)
        else:
            failed += 1
    logger.info(f"ارسال: {sent} نجح، {failed} فشل")
    return sent, failed

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

def create_tasbih_flex(user_id):
    counts = tasbih_counts.get(user_id, {key: 0 for key in TASBIH_KEYS})
    
    total = sum(counts.values())
    total_max = 33 * 4
    percentage = int((total / total_max) * 100)
    
    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "بوت 85",
                    "size": "md",
                    "weight": "bold",
                    "color": "#ffffff",
                    "align": "center"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": str(total),
                            "size": "xxl",
                            "weight": "bold",
                            "color": "#ffffff",
                            "align": "center"
                        },
                        {
                            "type": "text",
                            "text": f"{percentage}%",
                            "size": "xs",
                            "color": "#808080",
                            "align": "center",
                            "margin": "sm"
                        }
                    ],
                    "paddingAll": "15px",
                    "cornerRadius": "10px",
                    "backgroundColor": "#1a1a1a",
                    "borderWidth": "1px",
                    "borderColor": "#404040",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        create_tasbih_row("استغفر الله", counts),
                        create_tasbih_row("سبحان الله", counts, "xs"),
                        create_tasbih_row("الحمد لله", counts, "xs"),
                        create_tasbih_row("الله أكبر", counts, "xs")
                    ],
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                create_tasbih_button("استغفر الله", user_id),
                                create_tasbih_button("سبحان الله", user_id)
                            ],
                            "spacing": "xs"
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                create_tasbih_button("الحمد لله", user_id),
                                create_tasbih_button("الله أكبر", user_id)
                            ],
                            "spacing": "xs",
                            "margin": "xs"
                        }
                    ],
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#303030"
                },
                {
                    "type": "text",
                    "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري @ 2025",
                    "size": "xxs",
                    "color": "#606060",
                    "align": "center",
                    "margin": "sm"
                }
            ],
            "paddingAll": "12px",
            "backgroundColor": "#0a0a0a",
            "spacing": "none"
        }
    }
    
    return FlexMessage(alt_text="التسبيح", contents=FlexContainer.from_dict(flex_content))

def create_tasbih_row(text, counts, margin=None):
    row = {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": text,
                "size": "xs",
                "color": "#ffffff" if counts.get(text, 0) >= 33 else "#808080",
                "flex": 2
            },
            {
                "type": "text",
                "text": f"{counts.get(text, 0)}/33",
                "size": "xs",
                "color": "#c0c0c0",
                "align": "end",
                "flex": 1
            }
        ],
        "paddingAll": "8px",
        "backgroundColor": "#ffffff08" if counts.get(text, 0) >= 33 else "#00000010",
        "cornerRadius": "5px"
    }
    if margin:
        row["margin"] = margin
    return row

def create_tasbih_button(text, user_id):
    return {
        "type": "button",
        "action": {
            "type": "postback",
            "label": text,
            "data": f"tasbih_{text}_{user_id}"
        },
        "style": "secondary",
        "color": "#404040",
        "height": "sm"
    }

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

def handle_links(event, user_id, gid):
    try:
        text = event.message.text.strip()
        if any(x in text.lower() for x in ["http://", "https://", "www."]):
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] == 2 and gid:
                name = get_group_member_name(gid, user_id)
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
    return any(s in text for s in salam)

VALID_COMMANDS = ["مساعدة", "فضل", "تسبيح", "ذكرني"]

def is_valid_command(text):
    txt = text.strip()
    if check_salam(text) or txt in VALID_COMMANDS:
        return True
    return False

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        gid = getattr(event.source, "group_id", None)

        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()

        ensure_user_counts(user_id)

        if gid and handle_links(event, user_id, gid):
            return

        if not is_valid_command(user_text):
            return

        text_lower = user_text.lower()

        if check_salam(user_text):
            reply_message(event.reply_token, "وعليكم السلام ورحمة الله وبركاته")
            return

        if text_lower == "مساعدة":
            help_text = "بوت 85\n\nتسبيح - نافذة التسبيح التفاعلية\nفضل - فضل العبادات\nذكرني - ذكر أو دعاء عشوائي"
            reply_message(event.reply_token, help_text)
            return

        if text_lower == "فضل":
            reply_message(event.reply_token, get_next_fadl())
            return

        if text_lower == "تسبيح":
            flex_msg = create_tasbih_flex(user_id)
            reply_message(event.reply_token, flex_msg)
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
            except Exception as e:
                logger.error(f"خطأ ذكرني: {e}")
            return

    except Exception as e:
        logger.error(f"خطأ معالجة: {e}")

@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        data = event.postback.data
        
        if data.startswith("tasbih_"):
            parts = data.replace("tasbih_", "").rsplit("_", 1)
            if len(parts) != 2:
                return
            
            tasbih_text = parts[0]
            user_id = parts[1]
            
            ensure_user_counts(user_id)
            counts = tasbih_counts[user_id]
            
            if tasbih_text not in TASBIH_KEYS:
                return
            
            if counts[tasbih_text] < TASBIH_LIMITS:
                counts[tasbih_text] += 1
                save_data()
                
                count_now = counts[tasbih_text]
                reply_message(event.reply_token, f"{tasbih_text} ({count_now}/33)")
                
                if count_now == TASBIH_LIMITS:
                    time.sleep(0.5)
                    target_id = getattr(event.source, "group_id", None) or user_id
                    send_message(target_id, f"اكتمل {tasbih_text} - بارك الله فيك")
                    
                    if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                        time.sleep(0.5)
                        send_message(target_id, "اكتملت جميع الأذكار الأربعة\nجزاك الله خيرا")
            else:
                reply_message(event.reply_token, f"{tasbih_text} مكتمل (33/33)")
    
    except Exception as e:
        logger.error(f"خطأ postback: {e}")

def remind_all_on_start():
    try:
        time.sleep(10)
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        messages = content.get(category, [])
        if messages:
            broadcast_text(random.choice(messages))
    except Exception as e:
        logger.error(f"خطأ بدء: {e}")

@app.route("/", methods=["GET"])
def home():
    return "بوت 85 نشط", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "groups": len(target_groups)}), 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
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
    logger.info(f"بوت 85 - المنفذ {PORT}")
    threading.Thread(target=remind_all_on_start, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
