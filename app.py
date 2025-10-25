import os
import json
import random
import threading
import time
from datetime import datetime
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("❌ تأكد من وضع مفاتيح LINE في ملف .env")

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ———————————
# 🔹 تحميل البيانات والمحتوى
# ———————————

DATA_FILE = "data.json"
CONTENT_FILE = "content.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": [], "groups": [], "tasbih": {}, "notifications_off": {},
                "last_morning": {}, "last_evening": {}, "last_sleep": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_content():
    if not os.path.exists(CONTENT_FILE):
        return {"duas": ["اللهم اغفر لنا"], "adhkar": ["سبحان الله"],
                "hadiths": ["حديث شريف"], "quran": ["آية قرآنية"],
                "morning": ["أذكار الصباح"], "evening": ["أذكار المساء"],
                "sleep": ["أذكار النوم"]}
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
content = load_content()

# ———————————
# 🕌 وظائف البوت
# ———————————

def send_message(to, text):
    try:
        line_bot_api.push_message(to, TextSendMessage(text=text))
        return True
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال إلى {to}: {e}")
        return False

def send_broadcast(text):
    for uid in data["users"]:
        if uid not in data["notifications_off"]:
            send_message(uid, text)
            time.sleep(0.5)
    for gid in data["groups"]:
        if gid not in data["notifications_off"]:
            send_message(gid, text)
            time.sleep(0.5)

# رسالة ترحيب
def send_welcome_message(target_id, is_group=False):
    welcome_text = """🌙 *السلام عليكم ورحمة الله وبركاته*

✨ مرحبًا بك في بوت *ذكّرني*

📿 سيساعدك هذا البوت على:
• تذكّر أذكار الصباح والمساء والنوم
• متابعة التسبيح اليومي
• الحصول على أدعية وآيات قرآنية

🔹 اكتب *مساعدة* لعرض قائمة الأوامر

🤲 جزاك الله خيرًا"""
    try:
        send_message(target_id, welcome_text)
        return True
    except Exception as e:
        print(f"⚠️ خطأ في إرسال رسالة الترحيب: {e}")
        return False

# ———————————
# 📿 نظام التسبيح
# ———————————

tasbih_phrases = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله"]

def handle_tasbih(user_id, text):
    if user_id not in data["tasbih"]:
        data["tasbih"][user_id] = {p: 0 for p in tasbih_phrases}

    user_tasbih = data["tasbih"][user_id]
    if text in tasbih_phrases:
        user_tasbih[text] += 1
        save_data()
        count = user_tasbih[text]
        if count < 33:
            return f"📿 {text} ({count}/33)"
        elif count == 33:
            msg = f"🎉 أحسنت! أكملت 33 مرة من '{text}'!"
            if all(v >= 33 for v in user_tasbih.values()):
                msg += "\n\n🌙 *تهانينا!* أكملت جميع الأذكار الأربعة.\nجزاك الله خيرًا ❤️"
                data["tasbih"][user_id] = {p: 0 for p in tasbih_phrases}
                save_data()
            return msg
        else:
            return f"✅ أكملت {text} مسبقًا. جرّب ذكرًا آخر."
    return None

# ———————————
# ⏰ التذكيرات اليومية
# ———————————

def send_morning_adhkar():
    today = datetime.now().date().isoformat()
    for uid in data["users"]:
        if uid not in data["notifications_off"] and data["last_morning"].get(uid) != today:
            msg = random.choice(content.get("morning", ["أذكار الصباح"]))
            send_message(uid, f"🌅 *أذكار الصباح*\n\n{msg}")
            data["last_morning"][uid] = today
            time.sleep(0.5)
    for gid in data["groups"]:
        if gid not in data["notifications_off"] and data["last_morning"].get(gid) != today:
            msg = random.choice(content.get("morning", ["أذكار الصباح"]))
            send_message(gid, f"🌅 *أذكار الصباح*\n\n{msg}")
            data["last_morning"][gid] = today
            time.sleep(0.5)
    save_data()

def send_evening_adhkar():
    today = datetime.now().date().isoformat()
    for uid in data["users"]:
        if uid not in data["notifications_off"] and data["last_evening"].get(uid) != today:
            msg = random.choice(content.get("evening", ["أذكار المساء"]))
            send_message(uid, f"🌇 *أذكار المساء*\n\n{msg}")
            data["last_evening"][uid] = today
            time.sleep(0.5)
    for gid in data["groups"]:
        if gid not in data["notifications_off"] and data["last_evening"].get(gid) != today:
            msg = random.choice(content.get("evening", ["أذكار المساء"]))
            send_message(gid, f"🌇 *أذكار المساء*\n\n{msg}")
            data["last_evening"][gid] = today
            time.sleep(0.5)
    save_data()

def send_sleep_adhkar():
    today = datetime.now().date().isoformat()
    for uid in data["users"]:
        if uid not in data["notifications_off"] and data["last_sleep"].get(uid) != today:
            msg = random.choice(content.get("sleep", ["أذكار النوم"]))
            send_message(uid, f"🌙 *أذكار النوم*\n\n{msg}")
            data["last_sleep"][uid] = today
            time.sleep(0.5)
    for gid in data["groups"]:
        if gid not in data["notifications_off"] and data["last_sleep"].get(gid) != today:
            msg = random.choice(content.get("sleep", ["أذكار النوم"]))
            send_message(gid, f"🌙 *أذكار النوم*\n\n{msg}")
            data["last_sleep"][gid] = today
            time.sleep(0.5)
    save_data()

def send_random_reminder():
    category = random.choice(["duas", "adhkar", "hadiths", "quran"])
    msg = random.choice(content.get(category, ["لا يوجد محتوى"]))
    send_broadcast(msg)

def daily_scheduler():
    while True:
        now = datetime.now()
        hour = now.hour
        if 6 <= hour < 10:
            send_morning_adhkar()
            time.sleep(3600)
        elif 16 <= hour < 19:
            send_evening_adhkar()
            time.sleep(3600)
        elif 21 <= hour < 24:
            send_sleep_adhkar()
            time.sleep(3600)
        else:
            time.sleep(1800)

def random_reminder_scheduler():
    while True:
        time.sleep(random.randint(14400, 21600))
        send_random_reminder()

threading.Thread(target=daily_scheduler, daemon=True).start()
threading.Thread(target=random_reminder_scheduler, daemon=True).start()

# ———————————
# 🧠 معالجة الرسائل
# ———————————

@app.route("/", methods=["GET"])
def home():
    return "🕌 بوت ذكرني يعمل بنجاح!", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = getattr(event.source, "user_id", None)
    group_id = getattr(event.source, "group_id", None)
    text = event.message.text.strip()
    target_id = user_id or group_id

    # تسجيل المستخدمين والمجموعات مع إرسال رسالة ترحيبية
    is_new_user = False
    is_new_group = False

    if user_id and user_id not in data["users"]:
        data["users"].append(user_id)
        is_new_user = True
        save_data()
        send_welcome_message(user_id, is_group=False)

    if group_id and group_id not in data["groups"]:
        data["groups"].append(group_id)
        is_new_group = True
        save_data()
        send_welcome_message(group_id, is_group=True)

    # حماية من الروابط
    if "http://" in text or "https://" in text or "www." in text:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ يمنع إرسال الروابط هنا."))
        except:
            pass
        return

    # أمر: مساعدة
    if text.lower() == "مساعدة":
        help_text = """📖 قائمة أوامر بوت ذكرني

🔹 ذكرني
  إرسال تذكير فوري

🔹 تسبيح
  عرض حالة التسبيح لكل ذكر من الأذكار الأربعة

🔹 سبحان الله
  إضافة +1 على عداد "سبحان الله" (33 مرة لكل دورة)

🔹 الحمد لله
  إضافة +1 على عداد "الحمد لله" (33 مرة لكل دورة)

🔹 الله أكبر
  إضافة +1 على عداد "الله أكبر" (33 مرة لكل دورة)

🔹 استغفر الله
  إضافة +1 على عداد "استغفر الله" (33 مرة لكل دورة)"""
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        except:
            pass
        return

    # أمر: تشغيل
    if text.lower() == "تشغيل":
        if target_id in data["notifications_off"]:
            data["notifications_off"].remove(target_id)
            save_data()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ تم تفعيل التذكيرات التلقائية"))
        except:
            pass
        return

    # أمر: إيقاف
    if text.lower() == "إيقاف":
        if target_id not in data["notifications_off"]:
            data["notifications_off"].append(target_id)
            save_data()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⏸️ تم إيقاف التذكيرات التلقائية"))
        except:
            pass
        return

    # أمر: ذكرني (إرسال التذكير فقط بدون رسالة رد)
    if text.lower() == "ذكرني":
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        msg = random.choice(content.get(category, ["لا يوجد محتوى"]))
        send_broadcast(msg)
        return

    # أمر: تسبيح
    if text.lower() == "تسبيح":
        if target_id not in data["tasbih"]:
            data["tasbih"][target_id] = {p: 0 for p in tasbih_phrases}
            save_data()
        counts = data["tasbih"][target_id]
        status = (
            f"📿 *عداد التسبيح*\n\n"
            f"سبحان الله: {counts['سبحان الله']}/33\n"
            f"الحمد لله: {counts['الحمد لله']}/33\n"
            f"الله أكبر: {counts['الله أكبر']}/33\n"
            f"استغفر الله: {counts['استغفر الله']}/33"
        )
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except:
            pass
        return

    # معالجة التسبيح
    tasbih_result = handle_tasbih(target_id, text)
    if tasbih_result:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=tasbih_result))
        except:
            pass
        return

    # الرد الافتراضي
    if not is_new_user and not is_new_group:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🌙 اكتب *مساعدة* لعرض قائمة الأوامر."))
        except:
            pass

# ———————————
# 🚀 تشغيل التطبيق
# ———————————

if __name__ == "__main__":
    print(f"🚀 يعمل بوت ذكرني على المنفذ {PORT}")
    app.run(host="0.0.0.0", port=PORT)
