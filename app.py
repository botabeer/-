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
from dotenv import load_dotenv

# === LINE SDK v3 imports ===
from linebot.v3.messaging import MessagingApi, ApiClient, PushMessageRequest, ReplyMessageRequest
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage

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
    TASBIH_RESET_HOURS = 24

    REMINDER_INTERVAL = 3600  # seconds
    CONTENT_FILE = "content.json"

    @classmethod
    def validate(cls):
        if not cls.LINE_TOKEN or not cls.LINE_SECRET:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in .env")

Config.validate()

# === Logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Flask App ===
app = Flask(__name__)

# === LINE API Setup v3 ===
api_client = ApiClient(access_token=Config.LINE_TOKEN)
messaging_api = MessagingApi(api_client)
handler = WebhookHandler(channel_secret=Config.LINE_SECRET)

# === Content Manager ===
class ContentManager:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.content = self._load_content()
    
    def _load_content(self) -> Dict:
        try:
            with open(self.filepath, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading content: {e}")
            return {"athkar": [], "duas": [], "hadiths": [], "quran": []}
    
    def get_athkar(self) -> list:
        return self.content.get("athkar", [])
    
    def get_random_content(self) -> str:
        categories = [c for c in ["athkar","duas","hadiths","quran"] if self.content.get(c)]
        if not categories:
            return "لا يوجد محتوى متاح حالياً."
        category = random.choice(categories)
        data = self.content[category]
        return random.choice(data) if data else "لا يوجد محتوى متاح حالياً."

content_manager = ContentManager(Config.CONTENT_FILE)

# === Rate Limiter ===
class RateLimiter:
    def __init__(self):
        self.spam_records = defaultdict(list)
        self.link_counts = defaultdict(lambda: defaultdict(int))
        self.lock = threading.Lock()
    
    def check_rate_limit(self, user_id, group_id) -> bool:
        now = time.time()
        key = f"{group_id}:{user_id}"
        with self.lock:
            self.spam_records[key] = [t for t in self.spam_records[key] if now - t < Config.SPAM_PERIOD]
            self.spam_records[key].append(now)
            return len(self.spam_records[key]) <= Config.SPAM_LIMIT
    
    def check_links(self, text, group_id) -> bool:
        urls = re.findall(r'https?://[^\s]+', text)
        if not urls:
            return True
        with self.lock:
            for url in urls:
                self.link_counts[group_id][url] += 1
                if self.link_counts[group_id][url] > Config.LINK_LIMIT:
                    logger.warning(f"Link spam in {group_id}: {url}")
                    return False
        return True

rate_limiter = RateLimiter()

# === Tasbih Counter ===
class TasbihCounter:
    def __init__(self):
        self.counts = defaultdict(lambda: defaultdict(int))
        self.last_reset = defaultdict(lambda: datetime.now())
        self.lock = threading.Lock()
    
    def increment(self, user_id: str, tasbih_type: str) -> dict:
        with self.lock:
            if (datetime.now() - self.last_reset[user_id]).total_seconds()/3600 >= Config.TASBIH_RESET_HOURS:
                self.counts[user_id] = defaultdict(int)
                self.last_reset[user_id] = datetime.now()
            self.counts[user_id][tasbih_type] += 1
            count = self.counts[user_id][tasbih_type]
            return {"count": count, "limit": Config.TASBIH_LIMIT, "completed": count >= Config.TASBIH_LIMIT}
    
    def reset(self, user_id: str):
        with self.lock:
            self.counts[user_id] = defaultdict(int)
            self.last_reset[user_id] = datetime.now()

tasbih_counter = TasbihCounter()

# === Reminder Manager ===
class ReminderManager:
    def __init__(self):
        self.subscribed_groups: Set[str] = set()
        self.lock = threading.Lock()
        self.running = False
    
    def subscribe(self, group_id: str):
        with self.lock:
            self.subscribed_groups.add(group_id)
            logger.info(f"Group {group_id} subscribed")
    
    def unsubscribe(self, group_id: str):
        with self.lock:
            self.subscribed_groups.discard(group_id)
            logger.info(f"Group {group_id} unsubscribed")
    
    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self._loop, daemon=True).start()
    
    def _loop(self):
        while self.running:
            with self.lock:
                groups = list(self.subscribed_groups)
            if groups:
                text = content_manager.get_random_content()
                for gid in groups:
                    try:
                        messaging_api.push_message(PushMessageRequest(
                            to=gid, messages=[TextMessage(text=text)]
                        ))
                        logger.info(f"Reminder sent to {gid}")
                    except Exception as e:
                        logger.error(f"Failed to send to {gid}: {e}")
            time.sleep(Config.REMINDER_INTERVAL)

reminder_manager = ReminderManager()
reminder_manager.start()

# === Message Handling ===
class MessageHandler:
    @staticmethod
    def handle_tasbih(text: str, user_id: str) -> Optional[str]:
        athkar_list = content_manager.get_athkar()
        if not athkar_list:
            return None
        clean_text = text.replace(" ", "").lower()
        athkar_map = {a.replace(" ", "").lower(): a for a in athkar_list}
        if clean_text not in athkar_map:
            return None
        tasbih_type = athkar_map[clean_text]
        status = tasbih_counter.increment(user_id, tasbih_type)
        if status["completed"]:
            return f"✅ {tasbih_type} اكتمل! ({status['count']}/{status['limit']})"
        else:
            return f"📿 {tasbih_type} العدد: {status['count']}/{status['limit']}"
    
    @staticmethod
    def process(text: str, user_id: str, group_id: Optional[str]) -> Optional[str]:
        txt = text.lower().strip()
        if txt in ["مساعدة","الاوامر","help","؟"]:
            athkar_text = "\n".join([f"- {a}" for a in content_manager.get_athkar()[:5]]) or "- سبحان الله\n- الحمد لله\n- الله أكبر"
            return f"📿 التسبيح:\n{athkar_text}\n\nكل ذكر {Config.TASBIH_LIMIT} مرة\n\n• مساعدة • ذكرني • إعادة"
        if txt in ["إعادة","مسح","إعادة التسبيح","اعادة"]:
            tasbih_counter.reset(user_id)
            return "✅ تم مسح عداد التسبيح"
        if txt in ["ذكرني","ذكر","آية","حديث"]:
            return content_manager.get_random_content()
        if txt in ["تفعيل التذكير","تفعيل","اشتراك"] and group_id:
            reminder_manager.subscribe(group_id)
            return "✅ تم تفعيل التذكير التلقائي للمجموعة"
        if txt in ["إيقاف التذكير","إيقاف","إلغاء الاشتراك","ايقاف"] and group_id:
            reminder_manager.unsubscribe(group_id)
            return "✅ تم إيقاف التذكير التلقائي للمجموعة"
        return MessageHandler.handle_tasbih(text, user_id)

# === LINE Webhook Handler ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        group_id = getattr(event.source, "group_id", None)
        effective_id = user_id or group_id or "unknown"
        
        if group_id and user_id:
            if not rate_limiter.check_rate_limit(user_id, group_id):
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ توقف عن إرسال الرسائل بسرعة")]
                ))
                return
            if not rate_limiter.check_links(text, group_id):
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ تم حظر الرابط المكرر")]
                ))
                return
        
        response = MessageHandler.process(text, effective_id, group_id)
        if response:
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=response)]
            ))
    
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
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Internal error", 500
    return "OK"

@app.route("/")
def index():
    return jsonify({"status":"running","bot":"Islamic Reminder Bot","version":"2.0"})

# === Startup ===
if __name__ == "__main__":
    logger.info(f"Starting server on port {Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)
