import os
import random
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from threading import Lock
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# إعداد Flask والـ LINE API
# ═══════════════════════════════════════════════════════════
app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ═══════════════════════════════════════════════════════════
# متغيرات عامة
# ═══════════════════════════════════════════════════════════
DUAS = ["اللهم اغفر لي", "اللهم ارزقني رضاك", "اللهم ارحمني"]
HADITHS = ["عن النبي ﷺ قال...", "حديث شريف 2", "حديث شريف 3"]

# قاعدة البيانات (مثال SQLite)
import sqlite3
class Database:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path
        self.lock = Lock()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_active_users(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id FROM users
                    WHERE notifications_enabled = 1
                    ORDER BY last_active DESC
                """)
                return [row['user_id'] for row in cursor.fetchall()]
        except:
            return []

    def get_all_active_groups(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT group_id FROM groups
                    WHERE notifications_enabled = 1
                    ORDER BY created_at DESC
                """)
                return [row['group_id'] for row in cursor.fetchall()]
        except:
            return []

db = Database()

# Rate limiter بسيط
class RateLimiter:
    def can_send(self):
        return True, 0
rate_limiter = RateLimiter()

# Logger بسيط
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# ═══════════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════════
def get_random_quran_verse():
    verses = ["آية 1", "آية 2", "آية 3"]
    return random.choice(verses)

def get_current_time():
    return datetime.now()

def send_message_safe(to: str, text: str, retry: int = 3) -> bool:
    for attempt in range(retry):
        try:
            can_send, wait_time = rate_limiter.can_send()
            if not can_send:
                time.sleep(wait_time + 1)
            line_bot_api.push_message(to, TextSendMessage(text=text))
            return True
        except LineBotApiError as e:
            if e.status_code == 400:
                try:
                    with db.lock, db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM users WHERE user_id = ?", (to,))
                        cursor.execute("DELETE FROM groups WHERE group_id = ?", (to,))
                        conn.commit()
                except:
                    pass
                return False
            elif e.status_code == 429:
                time.sleep(30 * (attempt + 1))
            elif e.status_code == 403:
                return False
            else:
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)
        except:
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
    return False

def verify_user_valid(user_id: str) -> bool:
    try:
        profile = line_bot_api.get_profile(user_id)
        return True
    except LineBotApiError as e:
        return False
    except:
        return False

def send_bulk_messages(recipients: list, message: str, delay: float = 1.0):
    success = 0
    failed = 0
    total = len(recipients)
    for i, recipient in enumerate(recipients, 1):
        if send_message_safe(recipient, message):
            success += 1
        else:
            failed += 1
        if i % 10 == 0:
            time.sleep(delay * 2)
        else:
            time.sleep(delay)
    return success, failed

# ═══════════════════════════════════════════════════════════
# Webhook
# ═══════════════════════════════════════════════════════════
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ═══════════════════════════════════════════════════════════
# معالجة الرسائل
# ═══════════════════════════════════════════════════════════
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    target_id = event.source.user_id

    # أمر ذكرني
    if user_text.lower() in ["ذكرني", "تذكير", "ذكر"]:
        content_type = random.choice(['dua', 'hadith', 'quran'])
        if content_type == 'dua':
            content = f"🤲 {random.choice(DUAS)}"
        elif content_type == 'hadith':
            content = f"📿 {random.choice(HADITHS)}"
        else:
            content = get_random_quran_verse()
        timestamp = get_current_time().strftime("%H:%M")
        message = f"{content}\n\n━━━━━━━━━━━\n⏰ {timestamp}"
        users = db.get_all_active_users()
        groups = db.get_all_active_groups()
        if len(users) == 0 and len(groups) == 0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ لا يوجد مستخدمين مسجلين!")
            )
            return
        success_users = 0
        failed_users = 0
        success_groups = 0
        failed_groups = 0
        for i, user_id in enumerate(users):
            if send_message_safe(user_id, message):
                success_users += 1
            else:
                failed_users += 1
            if (i + 1) % 10 == 0:
                time.sleep(2.0)
            else:
                time.sleep(0.8)
        for i, group_id in enumerate(groups):
            if send_message_safe(group_id, message):
                success_groups += 1
            else:
                failed_groups += 1
            time.sleep(0.8)
        total_success = success_users + success_groups
        total_failed = failed_users + failed_groups
        confirmation = f"📣 تم إرسال التذكير\n{content}\n\nنجح: {total_success}, فشل: {total_failed}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=confirmation)
        )
        return

    # أمر اختبار
    if user_text.lower() in ["اختبار", "test", "تجربة"]:
        test_message = "✅ البوت يعمل بشكل صحيح!"
        if send_message_safe(target_id, test_message):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ تم إرسال رسالة اختبار!"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ فشل إرسال رسالة الاختبار!"))
        return

    # أمر عدد المستخدمين
    if user_text.lower() in ["عدد المستخدمين", "المستخدمين", "users"]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            total_users = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE notifications_enabled = 1")
            active_users = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) as count FROM groups")
            total_groups = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) as count FROM groups WHERE notifications_enabled = 1")
            active_groups = cursor.fetchone()['count']
        msg = f"المستخدمين: {total_users} (نشط: {active_users})\nالمجموعات: {total_groups} (نشطة: {active_groups})"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    # أمر تنظيف
    if user_text.lower() in ["تنظيف", "cleanup", "clean"]:
        users = db.get_all_active_users()
        invalid_users = []
        for user_id in users:
            if not verify_user_valid(user_id):
                invalid_users.append(user_id)
                with db.lock, db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                    conn.commit()
        result_msg = f"❌ تم حذف {len(invalid_users)} مستخدم غير صالح"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result_msg))
        return

# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
