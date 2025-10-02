from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json
from dotenv import load_dotenv

# ---------------- إعداد البوت ---------------- #
load_dotenv()
app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------------- تحميل المحتوى ---------------- #
CONTENT_FILE = "content.json"
with open(CONTENT_FILE, "r", encoding="utf-8") as f:
    content = json.load(f)

# ---------------- Webhook ---------------- #
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
        print("خطأ في التوقيع")
    return "OK", 200

# ---------------- معالجة الرسائل ---------------- #
# حفظ المستخدمين والقروبات مؤقتاً فقط أثناء تشغيل البوت
target_users = set()
target_groups = set()

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # تسجيل المستخدمين والقروبات
    if hasattr(event.source, 'group_id') and event.source.group_id:
        target_groups.add(event.source.group_id)
    else:
        target_users.add(user_id)

    # أمر ذكرني
    if user_text.lower() == "ذكرني":
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content[category])
        all_ids = list(target_groups) + list(target_users)
        for tid in all_ids:
            try:
                line_bot_api.push_message(tid, TextSendMessage(text=message))
            except:
                pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
