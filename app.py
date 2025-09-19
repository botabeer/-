from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import threading
import random

app = Flask(__name__)

# قراءة القيم من متغيرات البيئة
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# تهيئة البوت
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- بيانات البوت ---------------- #
subscribers = set()
auto_reminder_enabled = True
tasbih_limits = 33
tasbih_counts = {}  # { user_id: {"سبحان الله": n, "الحمد لله": m, "الله أكبر": k} }
links_count = {}  # عداد الروابط لكل مستخدم

def ensure_user_counts(uid):
    if uid not in tasbih_counts:
        tasbih_counts[uid] = {"سبحان الله": 0, "الحمد لله": 0, "الله أكبر": 0}

# النصوص الأساسية (مقتطفات لتوضيح المثال)
AZKAR_SABAH = "أذكار الصباح..."
AZKAR_MASAA = "أذكار المساء..."
AZKAR_NAWM = "أذكار النوم..."
AYAT_KURSI = "آية الكرسي..."
DUA_LIST = ["دعاء 1", "دعاء 2", "دعاء 3"]
HADITH_LIST = ["حديث 1", "حديث 2", "حديث 3"]

HELP_TEXT = """الأوامر المتاحة:
صباح - أذكار الصباح
مساء - أذكار المساء
نوم - أذكار النوم
آية - آية الكرسي
دعاء - دعاء عشوائي
حديث - حديث عشوائي
تسبيح - بدء عداد التسبيح
تشغيل - تفعيل التذكير التلقائي
إيقاف - إيقاف التذكير التلقائي
مساعدة - عرض هذه القائمة
"""

# ---------------- Flask Routes ---------------- #
@app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    threading.Thread(target=handle_async, args=(body, signature)).start()
    return "OK", 200

def handle_async(body, signature):
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("خطأ في التوقيع")

# ---------------- معالجة الرسائل ---------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # حماية الروابط المكررة
    if "http" in text or "https" in text:
        if user_id not in links_count:
            links_count[user_id] = 1  # أول رابط
        else:
            if links_count[user_id] == 1:  # التحذير عند المرة الثانية
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="الرجاء عدم تكرار الروابط")
                )
            links_count[user_id] = 2  # بعد التحذير، الثبات على 2 لتجنب التكرار
        return

    # أوامر البوت
    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return
    if text == "صباح":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_SABAH))
        return
    if text == "مساء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_MASAA))
        return
    if text == "نوم":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_NAWM))
        return
    if text == "آية":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AYAT_KURSI))
        return
    if text == "دعاء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(DUA_LIST)))
        return
    if text == "حديث":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(HADITH_LIST)))
        return
    if text == "تشغيل":
        subscribers.add(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تفعيل التذكير التلقائي"))
        return
    if text == "إيقاف":
        subscribers.discard(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف التذكير التلقائي"))
        return
    if text == "تسبيح":
        ensure_user_counts(user_id)
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return
    if text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        ensure_user_counts(user_id)
        if tasbih_counts[user_id][text] < tasbih_limits:
            tasbih_counts[user_id][text] += 1
            if tasbih_counts[user_id][text] >= tasbih_limits:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {text} ({tasbih_limits} مرة)"))
            else:
                counts = tasbih_counts[user_id]
                status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{text} مكتمل ({tasbih_limits} مرة)"))
        return

    # أي نص آخر نتجاهله
    return

# ---------------- تشغيل Flask ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
