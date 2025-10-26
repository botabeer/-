import os
import json
import random
import threading
import time
import re
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Set
from flask import Flask, request, jsonify
from linebot.models import MessageEvent, TextMessage
from linebot.v3.messaging import MessagingApi, PushMessageRequest, ReplyMessageRequest
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from dotenv import load_dotenv

# === Configuration ===
load_dotenv()

class Config:
    LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
    PORT = int(os.getenv("PORT", 5000))
    SPAM_LIMIT = 5
    SPAM_PERIOD = 10
    LINK_LIMIT = 2
    TASBIH_LIMIT = 33
    REMINDER_INTERVAL = 3600
    CONTENT_FILE = "content.json"

    @classmethod
    def validate(cls):
        if not cls.LINE_TOKEN or not cls.LINE_SECRET:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in .env")

Config.validate()

# === Logging ===
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === Flask App ===
app = Flask(__name__)

# Messaging API & Webhook Handler
messaging_api = MessagingApi()  # لا تمرر channel_access_token هنا
handler = WebhookHandler(channel_secret=Config.LINE_SECRET)

# === Content Manager ===
class ContentManager:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.content = self.load_content()

    def load_content(self) -> Dict:
        try:
            with open(self.filepath, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading content.json: {e}")
            return {"athkar": [], "duas": [], "hadiths": [], "quran": []}

    def get_athkar(self) -> list:
        return self.content.get("athkar", [])

    def get_random(self) -> str:
        categories = ["athkar", "duas", "hadiths", "quran"]
        available = [cat for cat in categories if self.content.get(cat)]
        if not available:
            return "لا يوجد محتوى متاح حالياً."
        cat = random.choice(available)
        return random.choice(self.content[cat])

content_manager = ContentManager(Config.CONTENT_FILE)

# === Rate Limiter ===
class RateLimiter:
    def __init__(self):
        self.spam_records = defaultdict(list)
        self.link_counts = defaultdict(lambda: defaultdict(int))
        self.lock = threading.Lock()

    def check_rate(self, user_id: str, group_id: str) -> bool:
        now = time.time()
        key = f"{group_id}:{user_id}"
        with self.lock:
            self.spam_records[key] = [t for t in self.spam_records[key] if now - t < Config.SPAM_PERIOD]
            self.spam_records[key].append(now)
            return len(self.spam_records[key]) <= Config.SPAM_LIMIT

    def check_links(self, text: str, group_id: str) -> bool:
        urls = re.findall(r'https?://[^\s]+', text)
        if not urls:
            return True
        with self.lock:
            for url in urls:
                self.link_counts[group_id][url] += 1
                if self.link_counts[group_id][url] > Config.LINK_LIMIT:
                    return False
        return True

rate_limiter = RateLimiter()

# === Tasbih Counter ===
class TasbihCounter:
    def __init__(self):
        self.counts = defaultdict(lambda: defaultdict(int))
        self.lock = threading.Lock()

    def increment(self, user_id: str, tasbih: str) -> dict:
        with self.lock:
            self.counts[user_id][tasbih] += 1
            count = self.counts[user_id][tasbih]
            return {"count": count, "completed": count >= Config.TASBIH_LIMIT}

    def reset(self, user_id: str):
        with self.lock:
            self.counts[user_id] = defaultdict(int)

tasbih_counter = TasbihCounter()

# === Reminder Manager ===
class ReminderManager:
    def __init__(self):
        self.groups: Set[str] = set()
        self.lock = threading.Lock()
        self.running = False

    def subscribe(self, group_id: str):
        with self.lock:
            self.groups.add(group_id)

    def unsubscribe(self, group_id: str):
        with self.lock:
            self.groups.discard(group_id)

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while self.running:
            with self.lock:
                groups = list(self.groups)
            text = content_manager.get_random()
            for gid in groups:
                try:
                    request = PushMessageRequest(to=gid, messages=[TextMessage(text=text)])
                    messaging_api.push_message(request)
                except Exception as e:
                    logger.error(f"Failed to send reminder to {gid}: {e}")
            time.sleep(Config.REMINDER_INTERVAL)

reminder_manager = ReminderManager()
reminder_manager.start()

# === LINE Message Handler ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        group_id = getattr(event.source, "group_id", None)
        effective_id = user_id or group_id or "unknown"

        # Rate limiting
        if group_id and user_id:
            if not rate_limiter.check_rate(user_id, group_id):
                messaging_api.reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="⚠️ توقف عن الإرسال")])
                )
                return
            if not rate_limiter.check_links(text, group_id):
                messaging_api.reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="⚠️ تم حظر الرابط المكرر")])
                )
                return

        # Commands
        response = None
        txt = text.lower()
        if txt in ["مساعدة", "help", "الاوامر", "؟"]:
            athkar_list = content_manager.get_athkar()[:5]
            athkar_text = "\n".join([f"- {a}" for a in athkar_list])
            response = f"📿 التسبيح:\n{athkar_text}\nكل ذكر {Config.TASBIH_LIMIT} مرة"
        elif txt in ["إعادة", "مسح"]:
            tasbih_counter.reset(effective_id)
            response = "✅ تم مسح عداد التسبيح"
        elif txt in ["ذكرني", "آية", "حديث"]:
            response = content_manager.get_random()
        elif txt in ["تفعيل التذكير", "تفعيل"] and group_id:
            reminder_manager.subscribe(group_id)
            response = "✅ تم تفعيل التذكير التلقائي"
        elif txt in ["إيقاف التذكير", "إيقاف"] and group_id:
            reminder_manager.unsubscribe(group_id)
            response = "✅ تم إيقاف التذكير التلقائي"
        else:
            # Tasbih counting
            athkar_list = content_manager.get_athkar()
            athkar_map = {a.replace(" ", "").lower(): a for a in athkar_list}
            clean_text = text.replace(" ", "").lower()
            if clean_text in athkar_map:
                tasbih_type = athkar_map[clean_text]
                status = tasbih_counter.increment(effective_id, tasbih_type)
                response = f"📿 {tasbih_type} العدد: {status['count']}/{Config.TASBIH_LIMIT}"
                if status["completed"]:
                    response += " ✅ اكتمل!"

        if response:
            messaging_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=response)])
            )
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)

# === Flask Routes ===
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK"

@app.route("/")
def index():
    return jsonify({"status": "running", "bot": "Islamic Reminder Bot"})

if __name__ == "__main__":
    logger.info(f"Starting server on port {Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT)
