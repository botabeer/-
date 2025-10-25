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
LINE_CHANNEL_ACCESS_TOKEN = os.getenv(“LINE_CHANNEL_ACCESS_TOKEN”)
LINE_CHANNEL_SECRET = os.getenv(“LINE_CHANNEL_SECRET”)
PORT = int(os.getenv(“PORT”, 5000))

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
raise ValueError(“❌ تأكد من وضع مفاتيح LINE في ملف .env”)

app = Flask(**name**)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# —————————––

# 🔹 تحميل البيانات والمحتوى

# —————————––

DATA_FILE = “data.json”
CONTENT_FILE = “content.json”
HELP_FILE = “help.txt”

def load_data():
if not os.path.exists(DATA_FILE):
return {“users”: [], “groups”: [], “tasbih”: {}, “notifications_off”: [],
“last_morning”: {}, “last_evening”: {}, “last_sleep”: {}}
with open(DATA_FILE, “r”, encoding=“utf-8”) as f:
return json.load(f)

def save_data():
with open(DATA_FILE, “w”, encoding=“utf-8”) as f:
json.dump(data, f, ensure_ascii=False, indent=2)

def load_content():
with open(CONTENT_FILE, “r”, encoding=“utf-8”) as f:
return json.load(f)

data = load_data()
content = load_content()

# —————————––

# 🕌 وظائف البوت

# —————————––

def send_message(to, text):
try:
line_bot_api.push_message(to, TextSendMessage(text=text))
except Exception as e:
print(f”⚠️ خطأ في الإرسال: {e}”)

def send_broadcast(text):
“”“إرسال رسالة لجميع المستخدمين والمجموعات (مع احترام إعدادات الإيقاف)”””
for uid in data[“users”]:
if uid not in data[“notifications_off”]:
send_message(uid, text)
for gid in data[“groups”]:
if gid not in data[“notifications_off”]:
send_message(gid, text)

# —————————––

# 📿 نظام التسبيح

# —————————––

tasbih_phrases = [“سبحان الله”, “الحمد لله”, “الله أكبر”, “استغفر الله”]

def handle_tasbih(user_id, text):
“”“معالجة التسبيح وإرجاع الرسالة المناسبة”””
if user_id not in data[“tasbih”]:
data[“tasbih”][user_id] = {p: 0 for p in tasbih_phrases}

```
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
```

# —————————––

# ⏰ نظام التذكير اليومي

# —————————––

def send_morning_adhkar():
“”“إرسال أذكار الصباح لكل مستخدم مرة واحدة يوميًا”””
today = datetime.now().date().isoformat()
for uid in data[“users”]:
if uid not in data[“notifications_off”] and data[“last_morning”].get(uid) != today:
msg = random.choice(content.get(“morning”, content.get(“adhkar”, [“أذكار الصباح”])))
send_message(uid, f”🌅 *أذكار الصباح*\n\n{msg}”)
data[“last_morning”][uid] = today
for gid in data[“groups”]:
if gid not in data[“notifications_off”] and data[“last_morning”].get(gid) != today:
msg = random.choice(content.get(“morning”, content.get(“adhkar”, [“أذكار الصباح”])))
send_message(gid, f”🌅 *أذكار الصباح*\n\n{msg}”)
data[“last_morning”][gid] = today
save_data()

def send_evening_adhkar():
“”“إرسال أذكار المساء لكل مستخدم مرة واحدة يوميًا”””
today = datetime.now().date().isoformat()
for uid in data[“users”]:
if uid not in data[“notifications_off”] and data[“last_evening”].get(uid) != today:
msg = random.choice(content.get(“evening”, content.get(“adhkar”, [“أذكار المساء”])))
send_message(uid, f”🌇 *أذكار المساء*\n\n{msg}”)
data[“last_evening”][uid] = today
for gid in data[“groups”]:
if gid not in data[“notifications_off”] and data[“last_evening”].get(gid) != today:
msg = random.choice(content.get(“evening”, content.get(“adhkar”, [“أذكار المساء”])))
send_message(gid, f”🌇 *أذكار المساء*\n\n{msg}”)
data[“last_evening”][gid] = today
save_data()

def send_sleep_adhkar():
“”“إرسال أذكار النوم لكل مستخدم مرة واحدة يوميًا”””
today = datetime.now().date().isoformat()
for uid in data[“users”]:
if uid not in data[“notifications_off”] and data[“last_sleep”].get(uid) != today:
msg = random.choice(content.get(“sleep”, content.get(“adhkar”, [“أذكار النوم”])))
send_message(uid, f”🌙 *أذكار النوم*\n\n{msg}”)
data[“last_sleep”][uid] = today
for gid in data[“groups”]:
if gid not in data[“notifications_off”] and data[“last_sleep”].get(gid) != today:
msg = random.choice(content.get(“sleep”, content.get(“adhkar”, [“أذكار النوم”])))
send_message(gid, f”🌙 *أذكار النوم*\n\n{msg}”)
data[“last_sleep”][gid] = today
save_data()

def send_random_reminder():
“”“إرسال ذكر عشوائي للجميع”””
category = random.choice([“duas”, “adhkar”, “hadiths”, “quran”])
msg = random.choice(content.get(category, [“لا يوجد محتوى”]))
send_broadcast(f”💫 *تذكير*\n\n{msg}”)

def daily_scheduler():
“”“جدولة الأذكار اليومية”””
while True:
now = datetime.now()
hour = now.hour

```
    # أذكار الصباح (6-10 صباحًا)
    if 6 <= hour < 10:
        send_morning_adhkar()
        time.sleep(3600)  # انتظار ساعة

    # أذكار المساء (4-7 مساءً)
    elif 16 <= hour < 19:
        send_evening_adhkar()
        time.sleep(3600)

    # أذكار النوم (9-12 ليلاً)
    elif 21 <= hour < 24:
        send_sleep_adhkar()
        time.sleep(3600)

    else:
        time.sleep(1800)  # فحص كل نصف ساعة
```

def random_reminder_scheduler():
“”“جدولة التذكيرات العشوائية كل 4-6 ساعات”””
while True:
time.sleep(random.randint(14400, 21600))  # 4-6 ساعات
send_random_reminder()

# تشغيل الجدولة في خيوط مستقلة

threading.Thread(target=daily_scheduler, daemon=True).start()
threading.Thread(target=random_reminder_scheduler, daemon=True).start()

# —————————––

# 🧠 معالجة الرسائل

# —————————––

@app.route(”/”, methods=[“GET”])
def home():
return “🕌 بوت ذكرني يعمل بنجاح!”, 200

@app.route(”/callback”, methods=[“POST”])
def callback():
signature = request.headers.get(“X-Line-Signature”, “”)
body = request.get_data(as_text=True)
try:
handler.handle(body, signature)
except InvalidSignatureError:
return “Invalid signature”, 400
return “OK”

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
user_id = event.source.user_id if hasattr(event.source, “user_id”) else None
group_id = event.source.group_id if hasattr(event.source, “group_id”) else None
text = event.message.text.strip()
target_id = user_id or group_id

```
# تسجيل المستخدمين والمجموعات تلقائيًا
if user_id and user_id not in data["users"]:
    data["users"].append(user_id)
    save_data()
if group_id and group_id not in data["groups"]:
    data["groups"].append(group_id)
    save_data()

# حماية من الروابط
if "http://" in text or "https://" in text or "www." in text:
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ يمنع إرسال الروابط هنا."))
    except:
        pass
    return

# أمر: مساعدة
if text.lower() == "مساعدة":
    try:
        with open(HELP_FILE, "r", encoding="utf-8") as f:
            help_text = f.read()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
    except:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📖 لا يوجد ملف مساعدة حاليًا"))
    return

# أمر: تشغيل
if text.lower() == "تشغيل":
    if target_id in data["notifications_off"]:
        data["notifications_off"].remove(target_id)
        save_data()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔔 تم تفعيل التذكيرات من جديد."))
        except:
            pass
    else:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ التذكيرات مفعلة بالفعل."))
        except:
            pass
    return

# أمر: إيقاف
if text.lower() == "إيقاف":
    if target_id not in data["notifications_off"]:
        data["notifications_off"].append(target_id)
        save_data()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔕 تم إيقاف التذكيرات مؤقتًا."))
        except:
            pass
    else:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ التذكيرات متوقفة بالفعل."))
        except:
            pass
    return

# أمر: ذكرني (إرسال تذكير فوري للجميع)
if text.lower() == "ذكرني":
    category = random.choice(["duas", "adhkar", "hadiths", "quran"])
    msg = random.choice(content.get(category, ["لا يوجد محتوى"]))
    
    # إرسال للجميع
    send_broadcast(f"💫 *ذكرني*\n\n{msg}")
    
    # الرد للمستخدم
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✅ تم إرسال التذكير للجميع.\n\n{msg}"))
    except:
        pass
    return

# أمر: تسبيح (عرض الحالة)
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

# رد افتراضي
try:
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🌙 اكتب 'مساعدة' لعرض قائمة الأوامر."))
except:
    pass
```

# —————————––

# 🚀 تشغيل التطبيق

# —————————––

if **name** == “**main**”:
print(f”🚀 يعمل بوت ذكرني على المنفذ {PORT}”)
app.run(host=“0.0.0.0”, port=PORT)
