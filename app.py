import os
import json
import threading
import logging
import random
import time
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    PostbackEvent
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# إعدادات LINE Bot
ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

# ملفات البيانات
DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
FADL_FILE = "fadl.json"
TASBIH_KEYS = ["استغفر الله", "سبحان الله", "الحمد لله", "الله أكبر"]

def load_json(file, default):
    if not os.path.exists(file):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# تحميل البيانات
data = load_json(DATA_FILE, {"groups": [], "users": [], "tasbih": {}, "last_reminder": 0})
target_groups = set(data.get("groups", []))
target_users = set(data.get("users", []))
tasbih_counts = data.get("tasbih", {})
last_reminder_time = data.get("last_reminder", 0)

content = load_json(CONTENT_FILE, {"duas": [], "adhkar": [], "hadiths": [], "quran": []})
fadl_content = load_json(FADL_FILE, {"fadl": []}).get("fadl", [])
fadl_index = 0

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {key: 0 for key in TASBIH_KEYS}
        save_all()

def save_all():
    data["groups"] = list(target_groups)
    data["users"] = list(target_users)
    data["tasbih"] = tasbih_counts
    data["last_reminder"] = last_reminder_time
    save_data()

def send_message(target_id, message):
    def send_async():
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                if isinstance(message, str):
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=target_id,
                            messages=[TextMessage(text=message)]
                        )
                    )
                else:
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=target_id,
                            messages=[message]
                        )
                    )
        except Exception as e:
            logger.error(f"فشل الإرسال إلى {target_id}: {e}")
    threading.Thread(target=send_async, daemon=True).start()

def reply_message(reply_token, message):
    def send_reply():
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                if isinstance(message, str):
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=message)]
                        )
                    )
                else:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[message]
                        )
                    )
        except Exception as e:
            logger.error(f"فشل الرد: {e}")
    threading.Thread(target=send_reply, daemon=True).start()

def create_tasbih_flex(user_id):
    ensure_user_counts(user_id)
    counts = tasbih_counts[user_id]
    
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
                    "color": "#E0E0E0",
                    "align": "center"
                },
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#3A3A3A"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "استغفر الله",
                                        "data": f"tasbih_استغفر الله_{user_id}"
                                    },
                                    "style": "secondary",
                                    "color": "#505050",
                                    "height": "sm"
                                },
                                {
                                    "type": "text",
                                    "text": f"({counts['استغفر الله']}/33)",
                                    "size": "xs",
                                    "color": "#B0B0B0",
                                    "align": "center",
                                    "margin": "xs"
                                }
                            ],
                            "flex": 1
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "سبحان الله",
                                        "data": f"tasbih_سبحان الله_{user_id}"
                                    },
                                    "style": "secondary",
                                    "color": "#505050",
                                    "height": "sm"
                                },
                                {
                                    "type": "text",
                                    "text": f"({counts['سبحان الله']}/33)",
                                    "size": "xs",
                                    "color": "#B0B0B0",
                                    "align": "center",
                                    "margin": "xs"
                                }
                            ],
                            "flex": 1
                        }
                    ],
                    "spacing": "xs",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "الحمد لله",
                                        "data": f"tasbih_الحمد لله_{user_id}"
                                    },
                                    "style": "secondary",
                                    "color": "#505050",
                                    "height": "sm"
                                },
                                {
                                    "type": "text",
                                    "text": f"({counts['الحمد لله']}/33)",
                                    "size": "xs",
                                    "color": "#B0B0B0",
                                    "align": "center",
                                    "margin": "xs"
                                }
                            ],
                            "flex": 1
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "الله أكبر",
                                        "data": f"tasbih_الله أكبر_{user_id}"
                                    },
                                    "style": "secondary",
                                    "color": "#505050",
                                    "height": "sm"
                                },
                                {
                                    "type": "text",
                                    "text": f"({counts['الله أكبر']}/33)",
                                    "size": "xs",
                                    "color": "#B0B0B0",
                                    "align": "center",
                                    "margin": "xs"
                                }
                            ],
                            "flex": 1
                        }
                    ],
                    "spacing": "xs",
                    "margin": "xs"
                },
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#3A3A3A"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "إعادة تعيين",
                        "data": f"reset_{user_id}"
                    },
                    "style": "secondary",
                    "color": "#404040",
                    "height": "sm",
                    "margin": "sm"
                },
                {
                    "type": "text",
                    "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري @ 2025",
                    "size": "xxs",
                    "color": "#707070",
                    "align": "center",
                    "margin": "sm"
                }
            ],
            "paddingAll": "15px",
            "backgroundColor": "#202020"
        }
    }
    return FlexMessage(alt_text="نافذة التسبيح", contents=FlexContainer.from_dict(flex_content))

def get_next_fadl():
    global fadl_index
    if not fadl_content:
        return "لا يوجد محتوى متاح"
    msg = fadl_content[fadl_index]
    fadl_index = (fadl_index + 1) % len(fadl_content)
    return msg

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    lower_text = user_text.lower()
    user_id = event.source.user_id
    gid = getattr(event.source, "group_id", None)

    if gid:
        target_groups.add(gid)
    else:
        target_users.add(user_id)

    ensure_user_counts(user_id)

    if lower_text == "تسبيح":
        flex_msg = create_tasbih_flex(user_id)
        reply_message(event.reply_token, flex_msg)

    elif lower_text == "ذكرني":
        try:
            global last_reminder_time
            current_time = time.time()
            time_diff = current_time - last_reminder_time
            
            # التحقق من مرور ساعة على الأقل (3600 ثانية)
            if time_diff < 3600:
                remaining = int((3600 - time_diff) / 60)
                reply_message(event.reply_token, f"يرجى الانتظار {remaining} دقيقة قبل إرسال تذكير جديد")
                return
            
            category = random.choice(["duas", "adhkar", "hadiths", "quran"])
            messages = content.get(category, [])
            if not messages:
                reply_message(event.reply_token, "لا يوجد محتوى متاح حالياً")
                return
            message = random.choice(messages)
            
            # إرسال للمجموعات والشخص الذي أرسل الأمر
            for g in target_groups:
                send_message(g, message)
            
            # الرد على الشخص مباشرة بالذكر
            reply_message(event.reply_token, message)
            
            last_reminder_time = current_time
            save_all()
            
        except Exception as e:
            logger.error(f"خطأ في أمر ذكرني: {e}")

    elif lower_text == "فضل":
        reply_message(event.reply_token, get_next_fadl())

    elif lower_text == "مساعدة":
        help_text = """الأوامر المتاحة

تسبيح - فتح نافذة التسبيح التفاعلية
ذكرني - إرسال ذكر عشوائي للجميع
فضل - عرض فضل عمل من الأعمال الصالحة
مساعدة - عرض هذه القائمة"""
        reply_message(event.reply_token, help_text)

    save_all()

@handler.add(PostbackEvent)
def handle_postback(event):
    data_post = event.postback.data
    
    if data_post.startswith("reset_"):
        user_id = data_post.replace("reset_", "")
        ensure_user_counts(user_id)
        tasbih_counts[user_id] = {key: 0 for key in TASBIH_KEYS}
        save_all()
        flex_msg = create_tasbih_flex(user_id)
        reply_message(event.reply_token, flex_msg)
        
    elif data_post.startswith("tasbih_"):
        parts = data_post.replace("tasbih_", "").rsplit("_", 1)
        if len(parts) != 2:
            return
        tasbih_text, user_id = parts
        ensure_user_counts(user_id)
        
        if tasbih_text in TASBIH_KEYS:
            max_count = 33
            
            if tasbih_counts[user_id][tasbih_text] < max_count:
                tasbih_counts[user_id][tasbih_text] += 1
                count = tasbih_counts[user_id][tasbih_text]
                save_all()
                
                if count == max_count:
                    response_text = f"{tasbih_text} ({count}/{max_count})\n\nتم إكمال {max_count} مرة\nبارك الله فيك"
                else:
                    response_text = f"{tasbih_text} ({count}/{max_count})"
                
                reply_message(event.reply_token, response_text)
            else:
                reply_message(event.reply_token, f"تم إكمال {tasbih_text} بالكامل\nاستخدم زر إعادة تعيين للبدء من جديد")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@app.route("/ping", methods=["GET"])
def ping():
    return "Bot is running", 200

@app.route("/", methods=["GET"])
def home():
    return "LINE Bot Server is Active", 200

if __name__ == "__main__":
    logger.info(f"بدء تشغيل البوت على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
