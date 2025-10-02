from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, json
from dotenv import load_dotenv

# -------------- إعداد البوت -------------- #
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -------------- تحميل المحتوى -------------- #
CONTENT_FILE = "content.json"
try:
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)
except Exception as e:
    print("خطأ في تحميل content.json:", e)
    content = {"duas": ["دعاء افتراضي"], "adhkar": ["ذكر افتراضي"], "hadiths": ["حديث افتراضي"]}

# -------------- Webhook -------------- #
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("خطأ في التوقيع")
    except Exception as e:
        print("خطأ عام:", e)
    return "OK", 200

# -------------- أمر ذكرني فقط -------------- #
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    if user_text.lower() == "ذكرني":
        # نختار عشوائي من كل الفئات
        import random
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content.get(category, ["لا يوجد محتوى"]))
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
        print(f"تم إرسال ذكرني للمستخدم: {user_id}")

# -------------- تشغيل السيرفر -------------- #
if __name__ == "__main__":
    print(f"Bot is running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
