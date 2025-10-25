import os
import json
import random
import threading
import time
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# إعداد التوقيت (UTC+3)
TIMEZONE = timezone(timedelta(hours=3))

def get_current_time():
    """الحصول على الوقت الحالي بتوقيت +3"""
    return datetime.now(TIMEZONE)

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
    """تحميل بيانات المستخدمين والمجموعات"""
    if not os.path.exists(DATA_FILE):
        return {
            "users": [],
            "groups": [],
            "tasbih": {},
            "notifications_off": [],
            "last_morning": {},
            "last_evening": {},
            "last_sleep": {}
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ خطأ في قراءة data.json، سيتم إنشاء ملف جديد")
        return {
            "users": [],
            "groups": [],
            "tasbih": {},
            "notifications_off": [],
            "last_morning": {},
            "last_evening": {},
            "last_sleep": {}
        }

def save_data():
    """حفظ البيانات بشكل آمن"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ خطأ في حفظ البيانات: {e}")

def load_content():
    """تحميل محتوى الأذكار والأدعية"""
    if not os.path.exists(CONTENT_FILE):
        return {
            "duas": ["اللهم اغفر لنا وارحمنا"],
            "adhkar": ["سبحان الله وبحمده"],
            "hadiths": ["من قال سبحان الله وبحمده مائة مرة حطت خطاياه وإن كانت مثل زبد البحر"],
            "quran": ["بسم الله الرحمن الرحيم"],
            "morning": ["أصبحنا وأصبح الملك لله"],
            "evening": ["أمسينا وأمسى الملك لله"],
            "sleep": ["باسمك اللهم أموت وأحيا"]
        }
    try:
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ خطأ في قراءة content.json، سيتم استخدام المحتوى الافتراضي")
        return {
            "duas": ["اللهم اغفر لنا وارحمنا"],
            "adhkar": ["سبحان الله وبحمده"],
            "hadiths": ["من قال سبحان الله وبحمده مائة مرة حطت خطاياه وإن كانت مثل زبد البحر"],
            "quran": ["بسم الله الرحمن الرحيم"],
            "morning": ["أصبحنا وأصبح الملك لله"],
            "evening": ["أمسينا وأمسى الملك لله"],
            "sleep": ["باسمك اللهم أموت وأحيا"]
        }

data = load_data()
content = load_content()

# ———————————
# 🕌 وظائف البوت
# ———————————

def send_message(to, text):
    """إرسال رسالة لمستخدم أو مجموعة محددة"""
    try:
        line_bot_api.push_message(to, TextSendMessage(text=text))
        return True
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال إلى {to}: {e}")
        return False

def send_broadcast(text):
    """إرسال رسالة لجميع المستخدمين والمجموعات (مع احترام إعدادات الإيقاف)"""
    success_count = 0
    fail_count = 0
    
    for uid in data["users"]:
        if uid not in data["notifications_off"]:
            if send_message(uid, text):
                success_count += 1
            else:
                fail_count += 1
            time.sleep(0.5)
    
    for gid in data["groups"]:
        if gid not in data["notifications_off"]:
            if send_message(gid, text):
                success_count += 1
            else:
                fail_count += 1
            time.sleep(0.5)
    
    print(f"✅ تم الإرسال إلى {success_count} متلقي، فشل {fail_count}")
    return success_count, fail_count

def send_welcome_message(target_id, is_group=False):
    """إرسال رسالة ترحيبية للمستخدمين أو المجموعات الجدد"""
    welcome_text = """🌙 السلام عليكم ورحمة الله وبركاته

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
    """معالجة عدّاد التسبيح"""
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
                # إعادة تعيين العدّاد
                data["tasbih"][user_id] = {p: 0 for p in tasbih_phrases}
                save_data()
            return msg
        else:
            return f"✅ أكملت {text} مسبقًا ({count}/33). جرّب ذكرًا آخر."
    
    return None

# ———————————
# ⏰ نظام التذكير اليومي
# ———————————

def send_morning_adhkar():
    """إرسال أذكار الصباح"""
    today = get_current_time().date().isoformat()
    
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
    print(f"✅ تم إرسال أذكار الصباح - {today}")

def send_evening_adhkar():
    """إرسال أذكار المساء"""
    today = get_current_time().date().isoformat()
    
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
    print(f"✅ تم إرسال أذكار المساء - {today}")

def send_sleep_adhkar():
    """إرسال أذكار النوم"""
    today = get_current_time().date().isoformat()
    
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
    print(f"✅ تم إرسال أذكار النوم - {today}")

def send_random_reminder():
    """إرسال تذكير عشوائي"""
    category = random.choice(["duas", "adhkar", "hadiths", "quran"])
    msg = random.choice(content.get(category, ["لا يوجد محتوى"]))
    send_broadcast(msg)
    print(f"✅ تم إرسال تذكير عشوائي من فئة: {category}")

def daily_scheduler():
    """جدولة التذكيرات اليومية"""
    print("🕐 بدأ جدول التذكيرات اليومية (UTC+3)")
    last_morning_hour = -1
    last_evening_hour = -1
    last_sleep_hour = -1
    
    while True:
        try:
            now = get_current_time()
            hour = now.hour
            
            # أذكار الصباح (6-10 صباحًا) - مرة واحدة فقط
            if 6 <= hour < 10 and last_morning_hour != hour:
                send_morning_adhkar()
                last_morning_hour = hour
            
            # أذكار المساء (4-7 مساءً) - مرة واحدة فقط
            elif 16 <= hour < 19 and last_evening_hour != hour:
                send_evening_adhkar()
                last_evening_hour = hour
            
            # أذكار النوم (9-12 ليلاً) - مرة واحدة فقط
            elif 21 <= hour < 24 and last_sleep_hour != hour:
                send_sleep_adhkar()
                last_sleep_hour = hour
            
            # إعادة تعيين العدادات في بداية اليوم الجديد
            if hour == 0:
                last_morning_hour = -1
                last_evening_hour = -1
                last_sleep_hour = -1
            
            time.sleep(1800)  # فحص كل 30 دقيقة
            
        except Exception as e:
            print(f"⚠️ خطأ في جدول التذكيرات: {e}")
            time.sleep(3600)

def random_reminder_scheduler():
    """جدولة التذكيرات العشوائية"""
    print("🔀 بدأ جدول التذكيرات العشوائية")
    while True:
        try:
            sleep_time = random.randint(14400, 21600)  # 4-6 ساعات
            time.sleep(sleep_time)
            send_random_reminder()
        except Exception as e:
            print(f"⚠️ خطأ في التذكيرات العشوائية: {e}")
            time.sleep(3600)

# تشغيل الجداول
threading.Thread(target=daily_scheduler, daemon=True).start()
threading.Thread(target=random_reminder_scheduler, daemon=True).start()

# ———————————
# 🧠 معالجة الرسائل
# ———————————

@app.route("/", methods=["GET"])
def home():
    """صفحة رئيسية للتأكد من عمل البوت"""
    return "🕌 بوت ذكرني يعمل بنجاح!", 200

@app.route("/callback", methods=["POST"])
def callback():
    """معالجة webhook من LINE"""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("⚠️ توقيع غير صالح")
        return "Invalid signature", 400
    except Exception as e:
        print(f"⚠️ خطأ في معالجة الطلب: {e}")
        return "Error", 500
    
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """معالجة الرسائل النصية"""
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
        print(f"✅ مستخدم جديد: {user_id}")

    if group_id and group_id not in data["groups"]:
        data["groups"].append(group_id)
        is_new_group = True
        save_data()
        send_welcome_message(group_id, is_group=True)
        print(f"✅ مجموعة جديدة: {group_id}")

    # حماية من الروابط
    if any(keyword in text for keyword in ["http://", "https://", "www."]):
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ يمنع إرسال الروابط هنا.")
            )
        except:
            pass
        return

    # أمر: مساعدة
    if text.lower() == "مساعدة":
        help_text = """╔═══════════════════╗
║  📖 أوامر بوت ذكرني  ║
╚═══════════════════╝

┌─ التذكيرات ─┐
│ 🔔 ذكرني
│ → إرسال تذكير فوري لجميع المستخدمين
│    (دعاء، ذكر، حديث، أو آية)
│
│ ⏰ تشغيل
│ → تفعيل التذكيرات التلقائية
│
│ ⏸️ إيقاف
│ → إيقاف التذكيرات التلقائية
└──────────────┘

┌─ التسبيح ─┐
│ 📿 تسبيح
│ → عرض عداد التسبيح الخاص بك
│
│ اكتب أحد الأذكار التالية:
│ • سبحان الله (0/33)
│ • الحمد لله (0/33)
│ • الله أكبر (0/33)
│ • استغفر الله (0/33)
│
│ 🎯 الهدف: إكمال 33 مرة لكل ذكر
└──────────────┘

┌─ التذكيرات التلقائية ─┐
│ 🌅 أذكار الصباح → 06:00 - 10:00
│ 🌇 أذكار المساء → 16:00 - 19:00
│ 🌙 أذكار النوم → 21:00 - 00:00
│ 🔀 تذكير عشوائي → كل 4-6 ساعات
└──────────────┘

💡 نصيحة: استخدم "ذكرني" لنشر تذكير
    لجميع أعضاء المجموعة فورًا!

🤲 جزاك الله خيرًا"""
        
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=help_text)
            )
        except:
            pass
        return

    # أمر: تشغيل
    if text.lower() == "تشغيل":
        if target_id in data["notifications_off"]:
            data["notifications_off"].remove(target_id)
            save_data()
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ تم تفعيل التذكيرات التلقائية")
            )
        except:
            pass
        return

    # أمر: إيقاف
    if text.lower() == "إيقاف":
        if target_id not in data["notifications_off"]:
            data["notifications_off"].append(target_id)
            save_data()
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⏸️ تم إيقاف التذكيرات التلقائية")
            )
        except:
            pass
        return

    # أمر: ذكرني (إرسال تذكير فوري لجميع المستخدمين)
    if text.lower() == "ذكرني":
        category = random.choice(["duas", "adhkar", "hadiths", "quran"])
        msg = random.choice(content.get(category, ["لا يوجد محتوى"]))
        
        # إرسال للجميع
        success, fail = send_broadcast(msg)
        
        try:
            # تأكيد للمرسل
            confirmation = f"📣 *تم إرسال التذكير*\n\n{msg}\n\n✅ وصل إلى {success} متلقي"
            if fail > 0:
                confirmation += f"\n⚠️ فشل الإرسال لـ {fail}"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=confirmation)
            )
        except Exception as e:
            print(f"⚠️ خطأ عند إرسال التأكيد: {e}")
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
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=status)
            )
        except:
            pass
        return

    # معالجة التسبيح
    tasbih_result = handle_tasbih(target_id, text)
    if tasbih_result:
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=tasbih_result)
            )
        except:
            pass
        return

    # رد افتراضي
    if not is_new_user and not is_new_group:
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🌙 اكتب *مساعدة* لعرض قائمة الأوامر.")
            )
        except:
            pass

# ———————————
# 🚀 تشغيل التطبيق
# ———————————

if __name__ == "__main__":
    print(f"🚀 يعمل بوت ذكرني على المنفذ {PORT}")
    print(f"🕐 التوقيت: UTC+3 (السعودية)")
    print(f"⏰ الوقت الحالي: {get_current_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 عدد المستخدمين: {len(data['users'])}")
    print(f"👥 عدد المجموعات: {len(data['groups'])}")
    app.run(host="0.0.0.0", port=PORT)
