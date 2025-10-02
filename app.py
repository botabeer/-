# app.py (مبسط ومصلح)
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

DATA_FILE = "data.json"
CONTENT_FILE = "content.json"
tasbih_limits = 33

# ---------- load / save ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": [], "groups": [], "rooms": [], "tasbih": {}}, f, ensure_ascii=False, indent=2)
        return set(), set(), set(), {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("users", [])), set(data.get("groups", [])), set(data.get("rooms", [])), data.get("tasbih", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": list(target_users),
            "groups": list(target_groups),
            "rooms": list(target_rooms),
            "tasbih": tasbih_counts
        }, f, ensure_ascii=False, indent=2)

target_users, target_groups, target_rooms, tasbih_counts = load_data()

# ---------- load content ----------
if not os.path.exists(CONTENT_FILE):
    # تجريبياً إذا الملف مش موجود، نضع مثال بسيط
    content = {
        "duas": ["اللهم اجعل عملي خالصاً لوجهك"],
        "verses": ["وما توفيقي إلا بالله"],
        "hadiths": ["عن النبي ﷺ: إنما الأعمال بالنيات"]
    }
else:
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)

# ---------- مساعدات عامة ----------
def ensure_user_counts(user_id):
    if not user_id:
        return
    if user_id not in tasbih_counts:
        tasbih_counts[user_id] = {"سبحان الله":0, "الحمد لله":0, "الله أكبر":0}

def push_to_all(text):
    """ابعت رسالة لكل المستخدمين والقروبات والروومز المسجلين"""
    all_ids = list(target_users) + list(target_groups) + list(target_rooms)
    for tid in all_ids:
        try:
            line_bot_api.push_message(tid, TextSendMessage(text=text))
        except Exception as e:
            print("push error to", tid, ":", e)

def random_message_from_content():
    # نتحقق من الفئات المتاحة ثم نختار عشوائي
    cats = [k for k in ("duas","verses","hadiths") if content.get(k)]
    if not cats:
        return "السلام عليكم"
    cat = random.choice(cats)
    return random.choice(content[cat])

# ---------- كشف الروابط ----------
links_count = {}
def handle_links(event, user_id):
    text = (event.message.text or "").strip()
    if any(s in text for s in ("http://","https://","www.")):
        if user_id:
            links_count[user_id] = links_count.get(user_id, 0) + 1
            if links_count[user_id] >= 2:
                try:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء عدم تكرار الروابط"))
                except Exception as e:
                    print("reply error (links):", e)
                return True
        else:
            # لا نعرف المستخدم (نرد تحذير عام)
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرسائل التي تحتوي روابط غير مسموح تكرارها"))
            except:
                pass
            return True
    return False

# ---------- Webhook ----------
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
        print("Invalid signature")
    except Exception as e:
        print("handler error:", e)
    return "OK", 200

# ---------- معالجة الرسائل ----------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = (event.message.text or "").strip()
    src_type = getattr(event.source, "type", None)
    user_id = getattr(event.source, "user_id", None)

    # تعيين target_id حسب نوع المصدر وتسجيله
    first_time = False
    if src_type == "group":
        target_id = getattr(event.source, "group_id", None)
        if target_id and target_id not in target_groups:
            target_groups.add(target_id)
            first_time = True
    elif src_type == "room":
        target_id = getattr(event.source, "room_id", None)
        if target_id and target_id not in target_rooms:
            target_rooms.add(target_id)
            first_time = True
    else:  # user
        target_id = user_id
        if target_id and target_id not in target_users:
            target_users.add(target_id)
            first_time = True

    save_data()
    ensure_user_counts(user_id)

    # إرسال رسالة عشوائية عند أول تواصل (إلى الهدف فقط)
    if first_time and target_id:
        msg = random_message_from_content()
        try:
            line_bot_api.push_message(target_id, TextSendMessage(text=msg))
        except Exception as e:
            print("push error (first_time):", e)

    # حماية الروابط
    if handle_links(event, user_id):
        return

    # أمر المساعدة: نرد للمستخدم ثم نبعث رسالة عشوائية للجميع
    if user_text.lower() == "مساعدة":
        help_text = """أوامر البوت المتاحة:

1. مساعدة
   - عرض قائمة الأوامر.

2. تسبيح
   - عرض عدد التسبيحات لكل كلمة لكل مستخدم.

3. سبحان الله / الحمد لله / الله أكبر
   - زيادة عدد التسبيحات لكل كلمة.
"""
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        except Exception as e:
            print("reply error (help):", e)
        # نرسل رسالة عشوائية لكل المسجلين
        msg = random_message_from_content()
        push_to_all(msg)
        return

    # أمر تسبيح: يعرض العد للمستخدم (يعمل فقط إذا user_id موجود)
    if user_text == "تسبيح":
        if not user_id:
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="أمر 'تسبيح' متاح في الخاص فقط."))
            except: pass
            return
        counts = tasbih_counts.get(user_id, {"سبحان الله":0,"الحمد لله":0,"الله أكبر":0})
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except Exception as e:
            print("reply error (tasbih):", e)
        return

    # زيادة التسبيح (تعمل في الخاص فقط لأننا نعتمد على user_id)
    if user_text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        if not user_id:
            try:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="أمر التسبيح غير متاح في هذا النوع من المحادثات."))
            except: pass
            return
        ensure_user_counts(user_id)
        # نفحص الحد
        if tasbih_counts[user_id].get(user_text,0) < tasbih_limits:
            tasbih_counts[user_id][user_text] = tasbih_counts[user_id].get(user_text,0) + 1
        save_data()
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        except Exception as e:
            print("reply error (inc tasbih):", e)
        return

if __name__ == "__main__":
    print("Starting bot...")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
