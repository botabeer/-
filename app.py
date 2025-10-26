import os
import json
import random
import threading
import time
import re
import logging
from collections import defaultdict
from datetime import datetime, timedelta
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
    """Centralized configuration"""
    LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
    PORT = int(os.getenv("PORT", 5000))
    
    # Rate limiting
    SPAM_LIMIT = 5
    SPAM_PERIOD = 10
    LINK_LIMIT = 2
    
    # Tasbih settings
    TASBIH_LIMIT = 33
    TASBIH_RESET_HOURS = 24
    
    # Reminder settings
    REMINDER_INTERVAL = 3600  # seconds
    
    # Content file
    CONTENT_FILE = "content.json"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.LINE_TOKEN or not cls.LINE_SECRET:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in .env")

Config.validate()

# === Logging Setup ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Flask App Setup ===
app = Flask(__name__)
messaging_api = MessagingApi(channel_access_token=Config.LINE_TOKEN)
handler = WebhookHandler(channel_secret=Config.LINE_SECRET)

# === Content Manager ===
class ContentManager:
    """Manages loading and accessing Islamic content"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.content = self._load_content()
    
    def _load_content(self) -> Dict:
        """Load content from JSON file"""
        try:
            with open(self.filepath, encoding="utf-8") as f:
                content = json.load(f)
                logger.info(f"Content loaded successfully from {self.filepath}")
                return content
        except FileNotFoundError:
            logger.error(f"Content file not found: {self.filepath}")
            return {"athkar": [], "duas": [], "hadiths": [], "quran": []}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.filepath}: {e}")
            return {"athkar": [], "duas": [], "hadiths": [], "quran": []}
        except Exception as e:
            logger.error(f"Error loading content: {e}")
            return {"athkar": [], "duas": [], "hadiths": [], "quran": []}
    
    def get_athkar(self) -> list:
        return self.content.get("athkar", [])
    
    def get_random_content(self) -> str:
        """Get random content from all categories"""
        categories = ["athkar", "duas", "hadiths", "quran"]
        available_categories = [cat for cat in categories if self.content.get(cat)]
        
        if not available_categories:
            return "لا يوجد محتوى متاح حالياً."
        
        category = random.choice(available_categories)
        data = self.content[category]
        return random.choice(data) if data else "لا يوجد محتوى متاح حالياً."
    
    def reload(self):
        """Reload content from file"""
        self.content = self._load_content()

content_manager = ContentManager(Config.CONTENT_FILE)

# === Rate Limiter ===
class RateLimiter:
    """Handle rate limiting for spam protection"""
    
    def __init__(self):
        self.spam_records = defaultdict(list)
        self.link_counts = defaultdict(lambda: defaultdict(int))
        self.lock = threading.Lock()
    
    def check_rate_limit(self, user_id: str, group_id: str, 
                        limit: int = Config.SPAM_LIMIT, 
                        period: int = Config.SPAM_PERIOD) -> bool:
        """Check if user exceeded rate limit"""
        now = time.time()
        key = f"{group_id}:{user_id}"
        
        with self.lock:
            # Clean old records
            self.spam_records[key] = [
                t for t in self.spam_records[key] 
                if now - t < period
            ]
            # Add current request
            self.spam_records[key].append(now)
            
            return len(self.spam_records[key]) <= limit
    
    def check_links(self, text: str, group_id: str, 
                   limit: int = Config.LINK_LIMIT) -> bool:
        """Check if links are being spammed"""
        urls = re.findall(r'https?://[^\s]+', text)
        
        if not urls:
            return True
        
        with self.lock:
            for url in urls:
                self.link_counts[group_id][url] += 1
                if self.link_counts[group_id][url] > limit:
                    logger.warning(f"Link spam detected in {group_id}: {url}")
                    return False
        
        return True
    
    def reset_link_counts(self, group_id: str):
        """Reset link counts for a group"""
        with self.lock:
            if group_id in self.link_counts:
                del self.link_counts[group_id]

rate_limiter = RateLimiter()

# === Tasbih Counter ===
class TasbihCounter:
    """Handle tasbih counting with auto-reset"""
    
    def __init__(self):
        self.counts = defaultdict(lambda: defaultdict(int))
        self.last_reset = defaultdict(lambda: datetime.now())
        self.lock = threading.Lock()
    
    def _should_reset(self, user_id: str) -> bool:
        """Check if counter should be reset based on time"""
        hours_passed = (datetime.now() - self.last_reset[user_id]).total_seconds() / 3600
        return hours_passed >= Config.TASBIH_RESET_HOURS
    
    def increment(self, user_id: str, tasbih_type: str) -> dict:
        """Increment tasbih count and return status"""
        with self.lock:
            if self._should_reset(user_id):
                self.counts[user_id] = defaultdict(int)
                self.last_reset[user_id] = datetime.now()
            
            self.counts[user_id][tasbih_type] += 1
            count = self.counts[user_id][tasbih_type]
            
            return {
                "count": count,
                "limit": Config.TASBIH_LIMIT,
                "completed": count >= Config.TASBIH_LIMIT
            }
    
    def reset(self, user_id: str):
        """Manually reset counter"""
        with self.lock:
            self.counts[user_id] = defaultdict(int)
            self.last_reset[user_id] = datetime.now()
    
    def get_status(self, user_id: str) -> dict:
        """Get current tasbih status"""
        with self.lock:
            return dict(self.counts[user_id])

tasbih_counter = TasbihCounter()

# === Reminder Manager ===
class ReminderManager:
    """Manage automatic reminders for groups"""
    
    def __init__(self):
        self.subscribed_groups: Set[str] = set()
        self.lock = threading.Lock()
        self.running = False
    
    def subscribe(self, group_id: str):
        """Subscribe group to reminders"""
        with self.lock:
            self.subscribed_groups.add(group_id)
            logger.info(f"Group {group_id} subscribed to reminders")
    
    def unsubscribe(self, group_id: str):
        """Unsubscribe group from reminders"""
        with self.lock:
            self.subscribed_groups.discard(group_id)
            logger.info(f"Group {group_id} unsubscribed from reminders")
    
    def is_subscribed(self, group_id: str) -> bool:
        """Check if group is subscribed"""
        with self.lock:
            return group_id in self.subscribed_groups
    
    def start(self):
        """Start reminder thread"""
        if not self.running:
            self.running = True
            thread = threading.Thread(target=self._reminder_loop, daemon=True)
            thread.start()
            logger.info("Reminder thread started")
    
    def _reminder_loop(self):
        """Main reminder loop"""
        while self.running:
            try:
                self._send_reminders()
            except Exception as e:
                logger.error(f"Error in reminder loop: {e}")
            
            time.sleep(Config.REMINDER_INTERVAL)
    
    def _send_reminders(self):
        """Send reminders to subscribed groups"""
        with self.lock:
            groups = list(self.subscribed_groups)
        
        if not groups:
            return
        
        text = content_manager.get_random_content()
        
        for group_id in groups:
            try:
                request = PushMessageRequest(
                    to=group_id,
                    messages=[TextMessage(text=text)]
                )
                messaging_api.push_message(request)
                logger.info(f"Reminder sent to group {group_id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {group_id}: {e}")

reminder_manager = ReminderManager()

# === Message Handler ===
class MessageHandler:
    """Handle different types of messages"""
    
    @staticmethod
    def help_message() -> str:
        """Generate help message"""
        athkar_list = content_manager.get_athkar()
        athkar_text = "\n".join([f"- {athkar}" for athkar in athkar_list[:5]]) if athkar_list else "- سبحان الله\n- الحمد لله\n- الله أكبر"
        
        return (
            "🤲 بوت ذكرني الإسلامي\n\n"
            "📿 التسبيح:\n"
            f"{athkar_text}\n\n"
            f"كل ذكر {Config.TASBIH_LIMIT} مرة\n\n"
            "📋 الأوامر:\n"
            "• مساعدة - عرض هذه الرسالة\n"
            "• ذكرني - ذكر عشوائي\n"
            "• إعادة - مسح عداد التسبيح\n"
        )
    
    @staticmethod
    def handle_tasbih(text: str, user_id: str) -> Optional[str]:
        """Handle tasbih counting"""
        athkar_list = content_manager.get_athkar()
        
        if not athkar_list:
            return None
        
        # Normalize text for matching
        clean_text = text.replace(" ", "").lower()
        athkar_map = {
            athkar.replace(" ", "").lower(): athkar 
            for athkar in athkar_list
        }
        
        if clean_text not in athkar_map:
            return None
        
        tasbih_type = athkar_map[clean_text]
        status = tasbih_counter.increment(user_id, tasbih_type)
        
        if status["completed"]:
            return f"✅ {tasbih_type}\nاكتمل! ({status['count']}/{status['limit']}) 🎉"
        else:
            return f"📿 {tasbih_type}\nالعدد: {status['count']}/{status['limit']}"
    
    @staticmethod
    def process_message(text: str, user_id: str, group_id: Optional[str]) -> Optional[str]:
        """Process incoming message and return response"""
        text_lower = text.lower().strip()
        
        # Help command
        if text_lower in ["مساعدة", "الاوامر", "help", "؟", "الأوامر"]:
            return MessageHandler.help_message()
        
        # Reset tasbih
        if text_lower in ["إعادة", "مسح", "إعادة التسبيح", "اعادة"]:
            tasbih_counter.reset(user_id)
            return "✅ تم مسح عداد التسبيح"
        
        # Random reminder
        if text_lower in ["ذكرني", "ذكر", "آية", "حديث"]:
            return content_manager.get_random_content()
        
        # Subscribe to reminders (groups only)
        if text_lower in ["تفعيل التذكير", "تفعيل", "اشتراك"] and group_id:
            reminder_manager.subscribe(group_id)
            return "✅ تم تفعيل التذكير التلقائي للمجموعة\nسيتم إرسال تذكير كل ساعة"
        
        # Unsubscribe from reminders (groups only)
        if text_lower in ["إيقاف التذكير", "إيقاف", "إلغاء الاشتراك", "ايقاف"] and group_id:
            reminder_manager.unsubscribe(group_id)
            return "✅ تم إيقاف التذكير التلقائي للمجموعة"
        
        # Try tasbih
        return MessageHandler.handle_tasbih(text, user_id)

# === LINE Bot Event Handler ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """Handle incoming LINE messages"""
    try:
        text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        group_id = getattr(event.source, "group_id", None)
        
        # Use group_id as fallback for user_id
        effective_user_id = user_id or group_id or "unknown"
        
        # Rate limiting for groups
        if group_id and user_id:
            if not rate_limiter.check_rate_limit(user_id, group_id):
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="⚠️ توقف عن إرسال الرسائل")]
                    )
                )
                return
            
            if not rate_limiter.check_links(text, group_id):
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="⚠️ تم حظر الرابط المكرر")]
                    )
                )
                return
        
        # Process message
        response = MessageHandler.process_message(text, effective_user_id, group_id)
        
        # Send response if available
        if response:
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=response)]
                )
            )
    
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)

# === Flask Routes ===
@app.route("/callback", methods=["POST"])
def callback():
    """LINE webhook callback"""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        return "Invalid signature", 400
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return "Internal error", 500
    
    return "OK"

@app.route("/")
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "bot": "Islamic Reminder Bot",
        "version": "2.0"
    })

@app.route("/health")
def health():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "subscribed_groups": len(reminder_manager.subscribed_groups),
        "content_loaded": bool(content_manager.content)
    })

# === Application Startup ===
def initialize():
    """Initialize application"""
    logger.info("Starting Islamic Reminder Bot...")
    logger.info(f"Content categories: {list(content_manager.content.keys())}")
    reminder_manager.start()
    logger.info("Bot initialized successfully")

if __name__ == "__main__":
    initialize()
    logger.info(f"Starting server on port {Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)
