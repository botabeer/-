import os
import schedule
import time
from linebot import LineBotApi
from linebot.models import TextSendMessage
from dotenv import load_dotenv

# تحميل المتغيرات من .env
load_dotenv()
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

# IDs (مجموعات أو مستخدمين) - ضيفهم في .env
targets = os.getenv("TARGET_IDS", "").split(",")

def read_adhkar(filename):
    filepath = os.path.join("adhkar", filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return None

def send_to_all(filename):
    text = read_adhkar(filename)
    if text:
        for t in targets:
            if t.strip():
                line_bot_api.push_message(t.strip(), TextSendMessage(text=text))

# جدولة الإرسال
schedule.every().day.at("04:00").do(lambda: send_to_all("sabah.txt"))
schedule.every().day.at("16:00").do(lambda: send_to_all("masa.txt"))
schedule.every().day.at("22:00").do(lambda: send_to_all("nom.txt"))

print("📌 Auto adhkar sender started...")

while True:
    schedule.run_pending()
    time.sleep(60)
