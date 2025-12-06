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
            json.dump({
                "users": list(target_users), 
                "groups": list(target_groups), 
                "tasbih": tasbih_counts,
                "timezones": user_timezones,
                "notifications": notification_settings
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ حفظ: {e}")

data = load_json(DATA_FILE, {"users": [], "groups": [], "tasbih": {}, "timezones": {}, "notifications": {}})
target_users = set(data.get("users", []))
target_groups = set(data.get("groups", []))
tasbih_counts = data.get("tasbih", {})
user_timezones = data.get("timezones", {})
notification_settings = data.get("notifications", {})

content = load_json(CONTENT_FILE, {"duas": [], "adhkar": [], "hadiths": [], "quran": []})
fadl_content = load_json("fadl.json", {"fadl": []}).get("fadl", [])
morning_adhkar = load_json("morning_adhkar.json", {"adhkar": []}).get("adhkar", [])
evening_adhkar = load_json("evening_adhkar.json", {"adhkar": []}).get("adhkar", [])
sleep_adhkar = load_json("sleep_adhkar.json", {"adhkar": []}).get("adhkar", [])

TIMEZONES = {
    "الرياض": "Asia/Riyadh",
    "مكة": "Asia/Riyadh",
    "المدينة": "Asia/Riyadh",
    "جدة": "Asia/Riyadh",
    "الدمام": "Asia/Riyadh",
    "دبي": "Asia/Dubai",
    "أبوظبي": "Asia/Dubai",
    "الكويت": "Asia/Kuwait",
    "الدوحة": "Asia/Qatar",
    "المنامة": "Asia/Bahrain",
    "مسقط": "Asia/Muscat",
    "القاهرة": "Africa/Cairo",
    "بيروت": "Asia/Beirut",
    "عمان": "Asia/Amman",
    "دمشق": "Asia/Damascus",
    "بغداد": "Asia/Baghdad",
    "صنعاء": "Asia/Aden"
}

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

def send_message(target_id, message):
    try:
        # تحقق من إعدادات الإشعارات
        if target_id in notification_settings and not notification_settings[target_id]:
            return True
        
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            if isinstance(message, str):
                api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=message)]))
            else:
                api.push_message(PushMessageRequest(to=target_id, messages=[message]))
        return True
    except Exception as e:
        if "400" not in str(e) and "403" not in str(e):
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
    if uid not in notification_settings:
        notification_settings[uid] = True
        save_data()

def create_tasbih_flex(user_id):
    """إنشاء نافذة تسبيح دائرية أنيقة"""
    counts = tasbih_counts.get(user_id, {key: 0 for key in TASBIH_KEYS})
    
    # حساب إجمالي التقدم
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
                    "align": "center",
                    "color": "#ffffff",
                    "weight": "bold",
                    "margin": "none"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": str(total),
                            "size": "5xl",
                            "align": "center",
                            "color": "#ffffff",
                            "weight": "bold"
                        },
                        {
                            "type": "text",
                            "text": f"{percentage}%",
                            "size": "sm",
                            "align": "center",
                            "color": "#cccccc",
                            "margin": "sm"
                        }
                    ],
                    "margin": "lg",
                    "paddingAll": "30px",
                    "cornerRadius": "100px",
                    "borderWidth": "3px",
                    "borderColor": "#ffffff",
                    "width": "180px",
                    "height": "180px",
                    "justifyContent": "center"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "استغفر الله",
                                        "data": "tasbih_استغفر الله"
                                    },
                                    "style": "secondary",
                                    "color": "#ffffff",
                                    "height": "sm",
                                    "flex": 1
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "سبحان الله",
                                        "data": "tasbih_سبحان الله"
                                    },
                                    "style": "secondary",
                                    "color": "#ffffff",
                                    "height": "sm",
                                    "flex": 1
                                }
                            ],
                            "spacing": "sm"
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "الحمد لله",
                                        "data": "tasbih_الحمد لله"
                                    },
                                    "style": "secondary",
                                    "color": "#ffffff",
                                    "height": "sm",
                                    "flex": 1
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "الله أكبر",
                                        "data": "tasbih_الله أكبر"
                                    },
                                    "style": "secondary",
                                    "color": "#ffffff",
                                    "height": "sm",
                                    "flex": 1
                                }
                            ],
                            "spacing": "sm",
                            "margin": "sm"
                        },
                        {
                            "type": "separator",
                            "margin": "lg",
                            "color": "#444444"
                        },
                        {
                            "type": "text",
                            "text": "عبير الدوسري 2025",
                            "size": "xxs",
                            "color": "#888888",
                            "align": "center",
                            "margin": "md"
                        }
                    ],
                    "margin": "xl"
                }
            ],
            "paddingAll": "20px",
            "backgroundColor": "#1a1a1a"
        }
    }
    
    return FlexMessage(alt_text="التسبيح", contents=FlexContainer.from_dict(flex_content))

def create_timezone_flex():
    """إنشاء نافذة اختيار المنطقة"""
    cities = list(TIMEZONES.keys())
    buttons = []
    
    for i in range(0, len(cities), 2):
        row = {
            "type": "box",
            "layout": "horizontal",
            "contents": [],
            "spacing": "xs"
        }
        
        for j in range(2):
            if i + j < len(cities):
                city = cities[i + j]
                row["contents"].append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": city,
                        "data": f"timezone_{city}"
                    },
                    "style": "secondary",
                    "color": "#ffffff",
                    "height": "sm",
                    "flex": 1
                })
        
        buttons.append(row)
    
    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "اختر منطقتك",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "color": "#ffffff"
                },
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#444444"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "xs",
                    "contents": buttons
                }
            ],
            "paddingAll": "16px",
            "backgroundColor": "#1a1a1a"
        }
    }
    
    return FlexMessage(alt_text="اختر منطقتك", contents=FlexContainer.from_dict(flex_content))

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

VALID_COMMANDS = ["مساعدة", "فضل", "تسبيح", "استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر", "ذكرني", "منطقة", "معلومات", "ايقاف", "تفعيل"]

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

        if gid and gid not in target_groups:
            target_groups.add(gid)
            save_data()

        ensure_user_counts(user_id)

        if handle_links(event, user_id, gid):
            return

        if not is_valid_command(user_text):
            return

        text_lower = user_text.lower()

        if check_salam(user_text):
            reply_message(event.reply_token, "وعليكم السلام ورحمة الله وبركاته")
            return

        if text_lower == "مساعدة":
            help_text = "بوت 85\n\nذكرني - ذكر أو دعاء\nفضل - فضل العبادات\nتسبيح - نافذة التسبيح\nمنطقة - اختيار منطقتك\nايقاف - إيقاف الإشعارات\nتفعيل - تفعيل الإشعارات\nمعلومات - عن البوت"
            reply_message(event.reply_token, help_text)
            return

        if text_lower == "معلومات":
            info_text = "بوت 85\n\nبوت إسلامي للأذكار والأدعية\n\nتم إنشاء هذا البوت بواسطة\nعبير الدوسري\n2025"
            reply_message(event.reply_token, info_text)
            return

        if text_lower == "ايقاف":
            notification_settings[user_id] = False
            save_data()
            reply_message(event.reply_token, "تم إيقاف الإشعارات")
            return

        if text_lower == "تفعيل":
            notification_settings[user_id] = True
            save_data()
            reply_message(event.reply_token, "تم تفعيل الإشعارات")
            return

        if text_lower == "فضل":
            reply_message(event.reply_token, get_next_fadl())
            return

        if text_lower == "تسبيح":
            flex_msg = create_tasbih_flex(user_id)
            reply_message(event.reply_token, flex_msg)
            return

        if text_lower == "منطقة":
            flex_msg = create_timezone_flex()
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
                broadcast_text(message, exclude_user=user_id, exclude_group=gid)
            except Exception as e:
                logger.error(f"خطأ ذكرني: {e}")
            return

    except Exception as e:
        logger.error(f"خطأ معالجة: {e}")

@handler.add(PostbackEvent)
def handle_postback(event):
    """معالجة ضغط الأزرار - تحديث صامت"""
    try:
        user_id = event.source.user_id
        data = event.postback.data
        
        if data.startswith("tasbih_"):
            tasbih_text = data.replace("tasbih_", "")
            
            ensure_user_counts(user_id)
            counts = tasbih_counts[user_id]
            
            # حفظ الحالة السابقة
            was_complete = counts[tasbih_text] >= TASBIH_LIMITS
            
            # زيادة العدد
            if counts[tasbih_text] < TASBIH_LIMITS:
                counts[tasbih_text] += 1
                save_data()
            
            # إرسال رسالة نصية فقط عند الاكتمال
            if counts[tasbih_text] == TASBIH_LIMITS and not was_complete:
                reply_message(event.reply_token, f"تم اكتمال {tasbih_text}")
                
                if all(counts[k] >= TASBIH_LIMITS for k in TASBIH_KEYS):
                    time.sleep(0.5)
                    send_message(user_id, "تم اكتمال الأذكار الأربعة\nجزاك الله خيراً")
            else:
                # رد فارغ لتجنب خطأ الرد
                try:
                    reply_message(event.reply_token, ".")
                except:
                    pass
        
        elif data.startswith("timezone_"):
            city = data.replace("timezone_", "")
            user_timezones[user_id] = TIMEZONES.get(city, "Asia/Riyadh")
            save_data()
            reply_message(event.reply_token, f"تم اختيار {city}")
    
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
    return jsonify({"status": "ok", "users": len(target_users), "groups": len(target_groups)}), 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
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
