"""
🌙 بوت ذكرني الإسلامي - النسخة المحسّنة 2.0
==================================================
✨ ميزات جديدة:
- قاعدة بيانات SQLite
- Thread-safe operations
- Advanced error handling
- Caching system
- Rate limiting protection
- Logging system
- Backup automation
- New features (Quran audio, Islamic calendar, etc.)
"""

import os
import json
import random
import threading
import time
import requests
import logging
import shutil
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Optional, Dict, List, Tuple
import sqlite3
from contextlib import contextmanager

from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════
# ⚙️ إعداد النظام الأساسي
# ═══════════════════════════════════════════════════════════

# إعداد التوقيت
TIMEZONE = timezone(timedelta(hours=3))

def get_current_time():
    """الحصول على الوقت الحالي بتوقيت +3"""
    return datetime.now(TIMEZONE)

# تحميل متغيرات البيئة
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
PORT = int(os.getenv("PORT", 5000))
DATABASE_PATH = os.getenv("DATABASE_PATH", "islamic_bot.db")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("❌ تأكد من وضع مفاتيح LINE في ملف .env")

# ═══════════════════════════════════════════════════════════
# 📝 نظام Logging المحسّن
# ═══════════════════════════════════════════════════════════

os.makedirs("logs", exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 🗄️ قاعدة البيانات SQLite
# ═══════════════════════════════════════════════════════════

class Database:
    """مدير قاعدة البيانات مع thread-safety"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """الحصول على اتصال آمن بقاعدة البيانات"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        """إنشاء جداول قاعدة البيانات"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            
            # جدول المستخدمين
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    city TEXT DEFAULT 'Riyadh',
                    notifications_enabled INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'ar',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            
            # جدول المجموعات
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    group_id TEXT PRIMARY KEY,
                    group_name TEXT,
                    notifications_enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # جدول التسبيح
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasbih (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    type TEXT,
                    count INTEGER DEFAULT 0,
                    date TEXT,
                    UNIQUE(user_id, type, date)
                )
            """)
            
            # جدول تقدم القرآن
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quran_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    juz_number INTEGER,
                    completed INTEGER DEFAULT 0,
                    completed_at TIMESTAMP,
                    UNIQUE(user_id, juz_number)
                )
            """)
            
            # جدول سجل الأذكار
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS athkar_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    type TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # جدول الإحصائيات
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    count INTEGER DEFAULT 1,
                    date TEXT,
                    UNIQUE(user_id, action, date)
                )
            """)
            
            # جدول التخزين المؤقت
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("✅ تم إنشاء قاعدة البيانات بنجاح")
    
    def add_user(self, user_id: str, username: str = None):
        """إضافة مستخدم جديد"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, username, last_active)
                    VALUES (?, ?, ?)
                """, (user_id, username, get_current_time()))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"⚠️ خطأ في إضافة مستخدم: {e}")
                return False
    
    def add_group(self, group_id: str, group_name: str = None):
        """إضافة مجموعة جديدة"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO groups (group_id, group_name)
                    VALUES (?, ?)
                """, (group_id, group_name))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"⚠️ خطأ في إضافة مجموعة: {e}")
                return False
    
    def update_user_activity(self, user_id: str):
        """تحديث آخر نشاط للمستخدم"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET last_active = ? WHERE user_id = ?
            """, (get_current_time(), user_id))
            conn.commit()
    
    def get_user_city(self, user_id: str) -> str:
        """الحصول على مدينة المستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT city FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row['city'] if row else 'Riyadh'
    
    def set_user_city(self, user_id: str, city: str):
        """تعيين مدينة المستخدم"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET city = ? WHERE user_id = ?
            """, (city, user_id))
            conn.commit()
    
    def toggle_notifications(self, target_id: str, enabled: bool, is_group: bool = False):
        """تبديل التنبيهات"""
        table = "groups" if is_group else "users"
        id_col = "group_id" if is_group else "user_id"
        
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {table} SET notifications_enabled = ? WHERE {id_col} = ?
            """, (1 if enabled else 0, target_id))
            conn.commit()
    
    def are_notifications_enabled(self, target_id: str, is_group: bool = False) -> bool:
        """التحقق من تفعيل التنبيهات"""
        table = "groups" if is_group else "users"
        id_col = "group_id" if is_group else "user_id"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT notifications_enabled FROM {table} WHERE {id_col} = ?
            """, (target_id,))
            row = cursor.fetchone()
            return row['notifications_enabled'] == 1 if row else True
    
    def increment_tasbih(self, user_id: str, tasbih_type: str, date: str) -> int:
        """زيادة عداد التسبيح"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasbih (user_id, type, count, date)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, type, date)
                DO UPDATE SET count = count + 1
            """, (user_id, tasbih_type, date))
            
            cursor.execute("""
                SELECT count FROM tasbih
                WHERE user_id = ? AND type = ? AND date = ?
            """, (user_id, tasbih_type, date))
            
            conn.commit()
            row = cursor.fetchone()
            return row['count'] if row else 0
    
    def get_tasbih_counts(self, user_id: str, date: str) -> Dict[str, int]:
        """الحصول على عدادات التسبيح"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, count FROM tasbih
                WHERE user_id = ? AND date = ?
            """, (user_id, date))
            
            counts = {row['type']: row['count'] for row in cursor.fetchall()}
            return counts
    
    def reset_tasbih(self, user_id: str, date: str):
        """إعادة تعيين التسبيح"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM tasbih WHERE user_id = ? AND date = ?
            """, (user_id, date))
            conn.commit()
    
    def get_all_active_users(self) -> List[str]:
        """الحصول على جميع المستخدمين النشطين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM users
                WHERE notifications_enabled = 1
            """)
            return [row['user_id'] for row in cursor.fetchall()]
    
    def get_all_active_groups(self) -> List[str]:
        """الحصول على جميع المجموعات النشطة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT group_id FROM groups
                WHERE notifications_enabled = 1
            """)
            return [row['group_id'] for row in cursor.fetchall()]
    
    def log_athkar_sent(self, user_id: str, athkar_type: str):
        """تسجيل إرسال الأذكار"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO athkar_log (user_id, type, sent_at)
                VALUES (?, ?, ?)
            """, (user_id, athkar_type, get_current_time()))
            conn.commit()
    
    def was_athkar_sent_today(self, user_id: str, athkar_type: str) -> bool:
        """التحقق من إرسال الأذكار اليوم"""
        today = get_current_time().date().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM athkar_log
                WHERE user_id = ? AND type = ?
                AND date(sent_at) = ?
            """, (user_id, athkar_type, today))
            
            row = cursor.fetchone()
            return row['count'] > 0 if row else False
    
    def get_statistics(self, user_id: str, days: int = 7) -> Dict:
        """الحصول على إحصائيات المستخدم"""
        start_date = (get_current_time() - timedelta(days=days)).date().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # إحصائيات التسبيح
            cursor.execute("""
                SELECT type, SUM(count) as total
                FROM tasbih
                WHERE user_id = ? AND date >= ?
                GROUP BY type
            """, (user_id, start_date))
            
            tasbih_stats = {row['type']: row['total'] for row in cursor.fetchall()}
            
            # إحصائيات الأذكار
            cursor.execute("""
                SELECT type, COUNT(*) as count
                FROM athkar_log
                WHERE user_id = ? AND date(sent_at) >= ?
                GROUP BY type
            """, (user_id, start_date))
            
            athkar_stats = {row['type']: row['count'] for row in cursor.fetchall()}
            
            return {
                'tasbih': tasbih_stats,
                'athkar': athkar_stats
            }
    
    def set_cache(self, key: str, value: str, expires_in_seconds: int = 3600):
        """حفظ في الذاكرة المؤقتة"""
        expires_at = get_current_time() + timedelta(seconds=expires_in_seconds)
        
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache (key, value, expires_at)
                VALUES (?, ?, ?)
            """, (key, value, expires_at))
            conn.commit()
    
    def get_cache(self, key: str) -> Optional[str]:
        """الحصول من الذاكرة المؤقتة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value FROM cache
                WHERE key = ? AND expires_at > ?
            """, (key, get_current_time()))
            
            row = cursor.fetchone()
            return row['value'] if row else None
    
    def clean_expired_cache(self):
        """تنظيف الذاكرة المؤقتة المنتهية"""
        with self.lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM cache WHERE expires_at <= ?
            """, (get_current_time(),))
            conn.commit()
            logger.info(f"🧹 تم تنظيف {cursor.rowcount} سجل من الذاكرة المؤقتة")
    
    def backup(self) -> bool:
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        try:
            timestamp = get_current_time().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"islamic_bot_{timestamp}.db")
            
            with self.lock:
                shutil.copy2(self.db_path, backup_file)
            
            logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_file}")
            
            # حذف النسخ القديمة (أكثر من 7 أيام)
            self._cleanup_old_backups(days=7)
            
            return True
        except Exception as e:
            logger.error(f"⚠️ فشل النسخ الاحتياطي: {e}")
            return False
    
    def _cleanup_old_backups(self, days: int = 7):
        """حذف النسخ الاحتياطية القديمة"""
        try:
            cutoff_time = time.time() - (days * 86400)
            
            for filename in os.listdir(BACKUP_DIR):
                if filename.endswith('.db'):
                    filepath = os.path.join(BACKUP_DIR, filename)
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        logger.info(f"🗑️ تم حذف النسخة القديمة: {filename}")
        except Exception as e:
            logger.error(f"⚠️ خطأ في تنظيف النسخ القديمة: {e}")

# إنشاء instance من قاعدة البيانات
db = Database(DATABASE_PATH)

# ═══════════════════════════════════════════════════════════
# 🌐 Flask App & LINE Bot Setup
# ═══════════════════════════════════════════════════════════

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ═══════════════════════════════════════════════════════════
# 📚 المحتوى الإسلامي
# ═══════════════════════════════════════════════════════════

MORNING_ATHKAR = [
    "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ",
    "اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ النُّشُورُ",
    "أَصْبَحْنَا عَلَى فِطْرَةِ الْإِسْلَامِ، وَعَلَى كَلِمَةِ الْإِخْلَاصِ، وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ",
    "سُبْحَانَ اللهِ وَبِحَمْدِهِ عَدَدَ خَلْقِهِ، وَرِضَا نَفْسِهِ، وَزِنَةَ عَرْشِهِ، وَمِدَادَ كَلِمَاتِهِ",
    "اللَّهُمَّ عَافِنِي فِي بَدَنِي، اللَّهُمَّ عَافِنِي فِي سَمْعِي، اللَّهُمَّ عَافِنِي فِي بَصَرِي",
    "اللَّهُمَّ إِنِّي أَصْبَحْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ، وَمَلَائِكَتَكَ، وَجَمِيعَ خَلْقِكَ"
]

EVENING_ATHKAR = [
    "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ",
    "اللَّهُمَّ بِكَ أَمْسَيْنَا، وَبِكَ أَصْبَحْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ الْمَصِيرُ",
    "أَمْسَيْنَا عَلَى فِطْرَةِ الْإِسْلَامِ، وَعَلَى كَلِمَةِ الْإِخْلَاصِ، وَعَلَى دِينِ نَبِيِّنَا مُحَمَّدٍ ﷺ",
    "اللَّهُمَّ إِنِّي أَمْسَيْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ، وَمَلَائِكَتَكَ، وَجَمِيعَ خَلْقِكَ",
    "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ رَبِّ الْعَالَمِينَ"
]

SLEEP_ATHKAR = [
    "بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
    "اللَّهُمَّ إِنَّكَ خَلَقْتَ نَفْسِي وَأَنْتَ تَوَفَّاهَا، لَكَ مَمَاتُهَا وَمَحْيَاهَا",
    "اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ",
    "بِاسْمِكَ رَبِّي وَضَعْتُ جَنْبِي، وَبِكَ أَرْفَعُهُ",
    "اللَّهُمَّ أَسْلَمْتُ نَفْسِي إِلَيْكَ، وَفَوَّضْتُ أَمْرِي إِلَيْكَ"
]

DUAS = [
    "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ",
    "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ",
    "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنْ عَذَابِ جَهَنَّمَ، وَمِنْ عَذَابِ الْقَبْرِ",
    "رَبِّ اغْفِرْ لِي وَلِوَالِدَيَّ وَلِلْمُؤْمِنِينَ يَوْمَ يَقُومُ الْحِسَابُ",
    "اللَّهُمَّ إِنِّي أَسْأَلُكَ عِلْمًا نَافِعًا، وَرِزْقًا طَيِّبًا، وَعَمَلًا مُتَقَبَّلًا"
]

HADITHS = [
    "مَنْ قَالَ: سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، فِي يَوْمٍ مِائَةَ مَرَّةٍ، حُطَّتْ خَطَايَاهُ وَإِنْ كَانَتْ مِثْلَ زَبَدِ الْبَحْرِ",
    "الْمُؤْمِنُ الْقَوِيُّ خَيْرٌ وَأَحَبُّ إِلَى اللَّهِ مِنَ الْمُؤْمِنِ الضَّعِيفِ، وَفِي كُلٍّ خَيْرٌ",
    "أَحَبُّ الْأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ",
    "الطُّهُورُ شَطْرُ الْإِيمَانِ، وَالْحَمْدُ لِلَّهِ تَمْلَأُ الْمِيزَانَ",
    "مَنْ كَانَ يُؤْمِنُ بِاللَّهِ وَالْيَوْمِ الْآخِرِ فَلْيَقُلْ خَيْرًا أَوْ لِيَصْمُتْ"
]

QURAN_VERSES = [
    "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
    "فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ",
    "وَمَا خَلَقْتُ الْجِنَّ وَالْإِنسَ إِلَّا لِيَعْبُدُونِ",
    "وَلَا تَيْأَسُوا مِن رَّوْحِ اللَّهِ إِنَّهُ لَا يَيْأَسُ مِن رَّوْحِ اللَّهِ إِلَّا الْقَوْمُ الْكَافِرُونَ",
    "وَلَذِكْرُ اللَّهِ أَكْبَرُ"
]

TASBIH_TYPES = ["سبحان الله", "الحمد لله", "الله أكبر", "استغفر الله", "لا إله إلا الله"]
TASBIH_LIMIT = 33

# ═══════════════════════════════════════════════════════════
# 🛡️ Rate Limiter
# ═══════════════════════════════════════════════════════════

class RateLimiter:
    """حماية من تجاوز حدود الإرسال"""
    
    def __init__(self, max_per_minute: int = 10):
        self.max_per_minute = max_per_minute
        self.requests = []
        self.lock = threading.Lock()
    
    def can_send(self) -> Tuple[bool, float]:
        """التحقق من إمكانية الإرسال"""
        with self.lock:
            now = time.time()
            # إزالة الطلبات القديمة
            self.requests = [t for t in self.requests if now - t < 60]
            
            if len(self.requests) < self.max_per_minute:
                self.requests.append(now)
                return True, 0
            else:
                wait_time = 60 - (now - self.requests[0])
                return False, wait_time

rate_limiter = RateLimiter(max_per_minute=30)

# ═══════════════════════════════════════════════════════════
# 📤 نظام الإرسال المحسّن
# ═══════════════════════════════════════════════════════════

def send_message_safe(to: str, text: str, retry: int = 3) -> bool:
    """إرسال رسالة مع معالجة الأخطاء وإعادة المحاولة"""
    for attempt in range(retry):
        try:
            # التحقق من rate limit
            can_send, wait_time = rate_limiter.can_send()
            if not can_send:
                logger.warning(f"⏸️ Rate limit: انتظار {wait_time:.1f} ثانية")
                time.sleep(wait_time + 1)
            
            line_bot_api.push_message(to, TextSendMessage(text=text))
            return True
            
        except LineBotApiError as e:
            if e.status_code == 429:  # Rate limit
                wait = 30 * (attempt + 1)
                logger.warning(f"⏸️ Rate limit من LINE API: انتظار {wait} ثانية")
                time.sleep(wait)
            elif e.status_code == 400:  # Invalid user/group
                logger.error(f"❌ مستخدم/مجموعة غير صالحة: {to}")
                return False
            else:
                logger.error(f"⚠️ خطأ LINE API: {e}")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"⚠️ خطأ في الإرسال لـ {to}: {e}")
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
    
    return False

def send_bulk_messages(recipients: List[str], message: str, delay: float = 1.0) -> Tuple[int, int]:
    """إرسال رسائل جماعية مع تقرير النتائج"""
    success = 0
    failed = 0
    
    for i, recipient in enumerate(recipients):
        if send_message_safe(recipient, message):
            success += 1
        else:
            failed += 1
        
        # تأخير تدريجي
        if (i + 1) % 10 == 0:
            time.sleep(delay * 2)
        else:
            time.sleep(delay)
    
    logger.info(f"📊 إرسال جماعي: ✅ {success} نجح، ❌ {failed} فشل")
    return success, failed

# ═══════════════════════════════════════════════════════════
# 🕌 نظام أوقات الصلاة المحسّن
# ═══════════════════════════════════════════════════════════

def get_prayer_times(city: str = "Riyadh") -> Optional[Dict[str, str]]:
    """الحصول على أوقات الصلاة مع التخزين المؤقت"""
    today = get_current_time().strftime("%d-%m-%Y")
    cache_key = f"prayer_times_{city}_{today}"
    
    # محاولة الحصول من الذاكرة المؤقتة
    cached = db.get_cache(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass
    
    # جلب من API
    try:
        url = f"http://api.aladhan.com/v1/timingsByCity/{today}?city={city}&country=Saudi%20Arabia&method=4"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data_response = response.json()
        
        if data_response.get("code") != 200:
            logger.warning(f"⚠️ API returned code: {data_response.get('code')}")
            return None
        
        timings = data_response["data"]["timings"]
        result = {
            "الفجر": timings["Fajr"],
            "الشروق": timings["Sunrise"],
            "الظهر": timings["Dhuhr"],
            "العصر": timings["Asr"],
            "المغرب": timings["Maghrib"],
            "العشاء": timings["Isha"]
        }
        
        # حفظ في الذاكرة المؤقتة (24 ساعة)
        db.set_cache(cache_key, json.dumps(result, ensure_ascii=False), 86400)
        
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"⚠️ انتهت مهلة الاتصال بـ API للصلاة")
    except requests.exceptions.RequestException as e:
        logger.error(f"⚠️ خطأ في الشبكة: {e}")
    except (KeyError, TypeError) as e:
        logger.error(f"⚠️ خطأ في بنية البيانات: {e}")
    except Exception as e:
        logger.error(f"⚠️ خطأ غير متوقع: {e}")
    
    return None

def check_prayer_times():
    """التحقق من أوقات الصلاة وإرسال التنبيهات"""
    logger.info("🕌 بدأ نظام تنبيهات أوقات الصلاة")
    prayer_cache = {}
    
    while True:
        try:
            now = get_current_time()
            current_time = now.strftime("%H:%M")
            today = now.date().isoformat()
            
            # تجميع المستخدمين حسب المدينة
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT city, GROUP_CONCAT(user_id) as users
                    FROM users
                    WHERE notifications_enabled = 1 AND city IS NOT NULL
                    GROUP BY city
                """)
                
                cities_data = cursor.fetchall()
            
            for row in cities_data:
                city = row['city']
                users = row['users'].split(',') if row['users'] else []
                
                if not users:
                    continue
                
                # استخدام الذاكرة المؤقتة
                cache_key = f"{city}:{today}"
                if cache_key not in prayer_cache:
                    prayer_cache[cache_key] = get_prayer_times(city)
                
                prayer_times = prayer_cache[cache_key]
                if not prayer_times:
                    continue
                
                # التحقق من كل صلاة
                for prayer, time_str in prayer_times.items():
                    if prayer == "الشروق":  # تخطي الشروق
                        continue
                    
                    try:
                        prayer_time = datetime.strptime(time_str, "%H:%M")
                        alert_time = (prayer_time - timedelta(minutes=10)).strftime("%H:%M")
                        
                        if current_time == alert_time:
                            message = f"🕌 حان وقت صلاة {prayer}\n⏰ بعد 10 دقائق: {time_str}\n\nاللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَآلِ مُحَمَّدٍ"
                            
                            for user_id in users:
                                send_message_safe(user_id, message)
                                time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"⚠️ خطأ في معالجة {prayer}: {e}")
            
            # تنظيف الذاكرة المؤقتة
            if len(prayer_cache) > 100:
                prayer_cache.clear()
            
            time.sleep(60)  # فحص كل دقيقة
            
        except Exception as e:
            logger.error(f"⚠️ خطأ في التحقق من أوقات الصلاة: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════
# 📖 نظام القرآن الكريم المحسّن
# ═══════════════════════════════════════════════════════════

def get_random_quran_verse() -> str:
    """الحصول على آية قرآنية عشوائية مع التخزين المؤقت"""
    cache_key = f"quran_verse_{get_current_time().date().isoformat()}"
    
    # محاولة الحصول من الذاكرة المؤقتة
    cached = db.get_cache(cache_key)
    if cached:
        return cached
    
    try:
        url = "https://api.alquran.cloud/v1/ayah/random/ar.alafasy"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data_response = response.json()
        
        if data_response.get("code") == 200:
            ayah_data = data_response["data"]
            text = ayah_data["text"]
            surah_name = ayah_data["surah"]["name"]
            number = ayah_data["numberInSurah"]
            
            result = f"📖 {text}\n\n﴿ {surah_name} - آية {number} ﴾"
            
            # حفظ في الذاكرة المؤقتة (ساعة واحدة)
            db.set_cache(cache_key, result, 3600)
            
            return result
    except Exception as e:
        logger.error(f"⚠️ خطأ في جلب آية قرآنية: {e}")
    
    return f"📖 {random.choice(QURAN_VERSES)}"

def get_quran_progress(user_id: str) -> Dict:
    """الحصول على تقدم قراءة القرآن"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT juz_number, completed
            FROM quran_progress
            WHERE user_id = ?
            ORDER BY juz_number
        """, (user_id,))
        
        progress = {}
        for row in cursor.fetchall():
            progress[row['juz_number']] = row['completed']
        
        completed_count = sum(1 for v in progress.values() if v)
        current_juz = 1
        
        for i in range(1, 31):
            if not progress.get(i, False):
                current_juz = i
                break
        
        return {
            'current_juz': current_juz,
            'completed_juz': completed_count,
            'total_juz': 30,
            'percentage': (completed_count / 30) * 100
        }

def mark_juz_completed(user_id: str, juz_number: int) -> bool:
    """تسجيل إتمام جزء من القرآن"""
    if not (1 <= juz_number <= 30):
        return False
    
    with db.lock, db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO quran_progress
            (user_id, juz_number, completed, completed_at)
            VALUES (?, ?, 1, ?)
        """, (user_id, juz_number, get_current_time()))
        conn.commit()
        return True

# ═══════════════════════════════════════════════════════════
# 🌙 نظام الأذكار التلقائية المحسّن
# ═══════════════════════════════════════════════════════════

def send_athkar_to_users(athkar_type: str, athkar_list: List[str]):
    """إرسال الأذكار لجميع المستخدمين والمجموعات"""
    logger.info(f"📤 بدء إرسال {athkar_type}")
    
    # اختيار ذكر عشوائي
    athkar_text = random.choice(athkar_list)
    
    # رموز تعبيرية حسب النوع
    emoji_map = {
        'morning': '☀️',
        'evening': '🌙',
        'sleep': '😴'
    }
    emoji = emoji_map.get(athkar_type, '🌙')
    
    # تحضير الرسالة
    title_map = {
        'morning': 'أذكار الصباح',
        'evening': 'أذكار المساء',
        'sleep': 'أذكار النوم'
    }
    title = title_map.get(athkar_type, 'ذكر')
    
    message = f"{emoji} {title}\n\n{athkar_text}\n\n━━━━━━━━━━━\n⏰ {get_current_time().strftime('%H:%M')}"
    
    # إرسال للمستخدمين
    users = db.get_all_active_users()
    success_users = 0
    
    for user_id in users:
        if not db.was_athkar_sent_today(user_id, athkar_type):
            if send_message_safe(user_id, message):
                db.log_athkar_sent(user_id, athkar_type)
                success_users += 1
            time.sleep(0.5)
    
    # إرسال للمجموعات
    groups = db.get_all_active_groups()
    success_groups = 0
    
    for group_id in groups:
        if not db.was_athkar_sent_today(group_id, athkar_type):
            if send_message_safe(group_id, message):
                db.log_athkar_sent(group_id, athkar_type)
                success_groups += 1
            time.sleep(0.5)
    
    logger.info(f"✅ تم إرسال {athkar_type}: {success_users} مستخدم، {success_groups} مجموعة")

def daily_scheduler():
    """جدولة الأذكار اليومية"""
    logger.info("🕐 بدأ جدول التذكيرات اليومية (UTC+3)")
    
    last_sent = {
        'morning': None,
        'evening': None,
        'sleep': None
    }
    
    while True:
        try:
            now = get_current_time()
            today = now.date().isoformat()
            hour = now.hour
            minute = now.minute
            
            # أذكار الصباح (7:00 صباحاً)
            if hour == 7 and minute == 0 and last_sent['morning'] != today:
                send_athkar_to_users('morning', MORNING_ATHKAR)
                last_sent['morning'] = today
                time.sleep(3600)  # انتظر ساعة
            
            # أذكار المساء (5:00 مساءً)
            elif hour == 17 and minute == 0 and last_sent['evening'] != today:
                send_athkar_to_users('evening', EVENING_ATHKAR)
                last_sent['evening'] = today
                time.sleep(3600)
            
            # أذكار النوم (10:00 مساءً)
            elif hour == 22 and minute == 0 and last_sent['sleep'] != today:
                send_athkar_to_users('sleep', SLEEP_ATHKAR)
                last_sent['sleep'] = today
                time.sleep(3600)
            
            else:
                time.sleep(60)  # فحص كل دقيقة
                
        except Exception as e:
            logger.error(f"⚠️ خطأ في جدول الأذكار: {e}")
            time.sleep(60)

def random_reminders_scheduler():
    """جدولة التذكيرات العشوائية"""
    logger.info("🔀 بدأ جدول التذكيرات العشوائية")
    
    while True:
        try:
            # انتظار 4-6 ساعات
            sleep_time = random.randint(14400, 21600)
            time.sleep(sleep_time)
            
            # اختيار نوع المحتوى
            content_type = random.choice(['dua', 'hadith', 'quran'])
            
            if content_type == 'dua':
                content = f"🤲 {random.choice(DUAS)}"
            elif content_type == 'hadith':
                content = f"📿 {random.choice(HADITHS)}"
            else:
                content = get_random_quran_verse()
            
            timestamp = get_current_time().strftime("%H:%M")
            message = f"{content}\n\n━━━━━━━━━━━\n⏰ {timestamp}"
            
            # إرسال للجميع
            users = db.get_all_active_users()
            groups = db.get_all_active_groups()
            
            send_bulk_messages(users + groups, message, delay=0.8)
            
            logger.info(f"✅ تم إرسال تذكير عشوائي: {content_type}")
            
        except Exception as e:
            logger.error(f"⚠️ خطأ في التذكيرات العشوائية: {e}")
            time.sleep(3600)

# ═══════════════════════════════════════════════════════════
# 📿 نظام التسبيح المحسّن
# ═══════════════════════════════════════════════════════════

def get_tasbih_progress_text(user_id: str, today: str) -> str:
    """الحصول على نص تقدم التسبيح"""
    counts = db.get_tasbih_counts(user_id, today)
    
    lines = []
    for tasbih_type in TASBIH_TYPES:
        count = counts.get(tasbih_type, 0)
        percentage = min((count / TASBIH_LIMIT) * 100, 100)
        filled = int(percentage / 10)
        bar = "▓" * filled + "░" * (10 - filled)
        
        # إضافة علامة إكمال
        status = " ✅" if count >= TASBIH_LIMIT else ""
        
        lines.append(f"{tasbih_type}{status}\n{count}/{TASBIH_LIMIT}  {bar}")
    
    return "\n\n".join(lines)

def check_tasbih_completion(user_id: str, today: str) -> bool:
    """التحقق من إكمال جميع الأذكار"""
    counts = db.get_tasbih_counts(user_id, today)
    return all(counts.get(t, 0) >= TASBIH_LIMIT for t in TASBIH_TYPES)

# ═══════════════════════════════════════════════════════════
# 🔄 مهام الصيانة الدورية
# ═══════════════════════════════════════════════════════════

def maintenance_tasks():
    """مهام الصيانة الدورية"""
    logger.info("🔧 بدأ نظام الصيانة الدورية")
    
    while True:
        try:
            # كل 24 ساعة
            time.sleep(86400)
            
            logger.info("🔧 بدء مهام الصيانة اليومية...")
            
            # نسخ احتياطي
            db.backup()
            
            # تنظيف الذاكرة المؤقتة
            db.clean_expired_cache()
            
            # تنظيف السجلات القديمة (أكثر من 30 يوم)
            with db.lock, db.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = (get_current_time() - timedelta(days=30)).isoformat()
                
                cursor.execute("""
                    DELETE FROM athkar_log
                    WHERE sent_at < ?
                """, (cutoff_date,))
                
                deleted = cursor.rowcount
                conn.commit()
                
                logger.info(f"🧹 تم حذف {deleted} سجل قديم")
            
            logger.info("✅ اكتملت مهام الصيانة")
            
        except Exception as e:
            logger.error(f"⚠️ خطأ في مهام الصيانة: {e}")
            time.sleep(3600)

# ═══════════════════════════════════════════════════════════
# 🌐 Flask Routes
# ═══════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        "status": "running",
        "bot": "Islamic Reminder Bot v2.0",
        "timestamp": get_current_time().isoformat()
    }), 200

@app.route("/health", methods=["GET"])
def health_check():
    """فحص صحة البوت"""
    try:
        # فحص قاعدة البيانات
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()['count']
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "users": user_count,
            "timestamp": get_current_time().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"⚠️ فشل فحص الصحة: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route("/stats", methods=["GET"])
def get_stats():
    """الحصول على إحصائيات البوت"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM users")
            users_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM groups")
            groups_count = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT COUNT(*) as count FROM users
                WHERE notifications_enabled = 1
            """)
            active_users = cursor.fetchone()['count']
        
        return jsonify({
            "total_users": users_count,
            "total_groups": groups_count,
            "active_users": active_users,
            "timestamp": get_current_time().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"⚠️ خطأ في الإحصائيات: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/callback", methods=["POST"])
def callback():
    """معالج webhook من LINE"""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("⚠️ توقيع غير صالح")
        return "Invalid signature", 400
    except Exception as e:
        logger.error(f"⚠️ خطأ في معالجة الطلب: {e}")
        return "Error", 500
    
    return "OK", 200

# ═══════════════════════════════════════════════════════════
# 💬 معالج الرسائل المحسّن
# ═══════════════════════════════════════════════════════════

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """معالج الرسائل الرئيسي"""
    try:
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        group_id = getattr(event.source, "group_id", None)
        target_id = user_id or group_id
        is_group = group_id is not None
        
        # تسجيل المستخدم/المجموعة
        is_new = False
        if user_id:
            is_new = db.add_user(user_id)
            db.update_user_activity(user_id)
        if group_id:
            is_new = db.add_group(group_id) or is_new
        
        today = get_current_time().date().isoformat()
        
        # ════════════════════════════════════════════════
        # 🆘 مساعدة
        # ════════════════════════════════════════════════
        if user_text.lower() in ["مساعدة", "help", "؟"]:
            help_text = """ *بوت ذكرني الإسلامي*

━━━━━━━━━━━━━━━━━
📿 *التسبيح:*
• سبحان الله / الحمد لله
• الله أكبر / استغفر الله
• لا إله إلا الله
• تسبيح - عرض التقدم
• إعادة - إعادة العداد

🕌 *أوقات الصلاة:*
• مدينتي [اسم المدينة]
• أوقات الصلاة
• التنبيهات قبل 10 دقائق

📖 *القرآن الكريم:*
• آية - آية قرآنية
• ختمتي - تقدم القراءة
• قرأت جزء [رقم]
• إحصائياتي

🌙 *الأذكار:*
• أذكار الصباح
• أذكار المساء
• أذكار النوم
• دعاء - دعاء عشوائي
• حديث - حديث شريف

📊 *المتابعة:*
• إحصائياتي - إحصائياتك الأسبوعية
• تقريري - تقرير شامل

📨 *التحكم:*
• إيقاف - إيقاف التنبيهات
• تشغيل - تشغيل التنبيهات
• ذكرني - تذكير فوري للجميع

━━━━━━━━━━━━━━━━━
✨ *ميزات جديدة:*
• نظام إحصائيات محسّن
• متابعة تقدم القراءة
• تنبيهات أوقات الصلاة

جزاك الله خيراً 🖤"""
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=help_text)
            )
            return
        
        # ════════════════════════════════════════════════
        # 🏙️ تسجيل المدينة
        # ════════════════════════════════════════════════
        if user_text.lower().startswith("مدينتي"):
            if not user_id:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ هذا الأمر يعمل في الرسائل الخاصة فقط")
                )
                return
            
            city = user_text.replace("مدينتي", "").strip()
            if city:
                db.set_user_city(user_id, city)
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"✅ تم تسجيل مدينتك: {city}\n\n🕌 ستصلك تنبيهات الصلاة قبل 10 دقائق")
                )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ الرجاء كتابة اسم المدينة\nمثال: مدينتي الرياض")
                )
            return
        
        # ════════════════════════════════════════════════
        # 🕌 أوقات الصلاة
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أوقات الصلاة", "الصلاة", "مواقيت", "اوقات الصلاة"]:
            city = db.get_user_city(user_id) if user_id else "Riyadh"
            prayer_times = get_prayer_times(city)
            
            if prayer_times:
                msg = f"🕌 *أوقات الصلاة في {city}*\n\n"
                msg += f"🌅 الفجر: {prayer_times['الفجر']}\n"
                msg += f"☀️ الشروق: {prayer_times['الشروق']}\n"
                msg += f"🕌 الظهر: {prayer_times['الظهر']}\n"
                msg += f"🌤️ العصر: {prayer_times['العصر']}\n"
                msg += f"🌇 المغرب: {prayer_times['المغرب']}\n"
                msg += f"🌙 العشاء: {prayer_times['العشاء']}\n"
                msg += f"\n━━━━━━━━━━━\n📍 {city}"
                
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=msg)
                )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ عذراً، لم نستطع الحصول على أوقات الصلاة\nالرجاء المحاولة لاحقاً")
                )
            return
        
        # ════════════════════════════════════════════════
        # 📖 آية قرآنية
        # ════════════════════════════════════════════════
        if user_text.lower() in ["آية", "قرآن", "اية", "ايه"]:
            verse = get_random_quran_verse()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=verse)
            )
            return
        
        # ════════════════════════════════════════════════
        # 📊 تقدم القراءة
        # ════════════════════════════════════════════════
        if user_text.lower() in ["ختمتي", "القراءة", "تقدمي"]:
            progress = get_quran_progress(target_id)
            
            # رسم شريط التقدم
            percentage = progress['percentage']
            filled = int(percentage / 5)  # 20 خانة
            bar = "▓" * filled + "░" * (20 - filled)
            
            msg = f"📖 *تقدم قراءة القرآن الكريم*\n\n"
            msg += f"الجزء الحالي: {progress['current_juz']}\n"
            msg += f"الأجزاء المكتملة: {progress['completed_juz']}/{progress['total_juz']}\n\n"
            msg += f"{bar}\n"
            msg += f"{percentage:.1f}%\n"
            
            if progress['completed_juz'] == 30:
                msg += "\n🎉 *ماشاء الله تبارك الله!*\n"
                msg += "أتممت ختمة كاملة!\n"
                msg += "بارك الله فيك ونفع بك 💚"
            elif progress['completed_juz'] >= 15:
                msg += "\n✨ ممتاز! نصف الطريق!\n"
                msg += "واصل بارك الله فيك 💪"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # ✅ تسجيل قراءة جزء
        # ════════════════════════════════════════════════
        if user_text.lower().startswith(("قرأت جزء", "قرات جزء", "جزء")):
            try:
                # استخراج رقم الجزء
                parts = user_text.split()
                juz_num = None
                for part in parts:
                    if part.isdigit():
                        juz_num = int(part)
                        break
                
                if juz_num and 1 <= juz_num <= 30:
                    if mark_juz_completed(target_id, juz_num):
                        progress = get_quran_progress(target_id)
                        
                        msg = f"✨ *ماشاء الله تبارك الله!*\n\n"
                        msg += f"تم تسجيل إتمام الجزء {juz_num}\n"
                        msg += f"📊 التقدم: {progress['completed_juz']}/30\n"
                        
                        if progress['completed_juz'] == 30:
                            msg += "\n🎉🎉🎉\n*ختمة كاملة!*\n"
                            msg += "بارك الله فيك وجعلها في ميزان حسناتك 💚"
                        else:
                            msg += f"\nالجزء التالي: {progress['current_juz']}\n"
                            msg += "بارك الله فيك، واصل 💪"
                        
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text=msg)
                        )
                    else:
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="⚠️ حدث خطأ في التسجيل")
                        )
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="⚠️ الرجاء إدخال رقم جزء صحيح (1-30)\nمثال: قرأت جزء 5")
                    )
            except Exception as e:
                logger.error(f"⚠️ خطأ في تسجيل الجزء: {e}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ صيغة غير صحيحة\nمثال: قرأت جزء 5")
                )
            return
        
        # ════════════════════════════════════════════════
        # 🌅 أذكار الصباح
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أذكار الصباح", "اذكار الصباح", "الصباح"]:
            msg = "☀️ *أذكار الصباح*\n\n"
            msg += "\n\n━━━━━━━━━━━\n\n".join(MORNING_ATHKAR[:3])
            msg += "\n\n━━━━━━━━━━━\n💡 نصيحة: اقرأها 3 مرات"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 🌇 أذكار المساء
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أذكار المساء", "اذكار المساء", "المساء"]:
            msg = "🌙 *أذكار المساء*\n\n"
            msg += "\n\n━━━━━━━━━━━\n\n".join(EVENING_ATHKAR[:3])
            msg += "\n\n━━━━━━━━━━━\n💡 نصيحة: اقرأها 3 مرات"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 😴 أذكار النوم
        # ════════════════════════════════════════════════
        if user_text.lower() in ["أذكار النوم", "اذكار النوم", "النوم"]:
            msg = "😴 *أذكار النوم*\n\n"
            msg += "\n\n━━━━━━━━━━━\n\n".join(SLEEP_ATHKAR[:3])
            msg += "\n\n━━━━━━━━━━━\n💤 تصبح على خير"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 🤲 دعاء
        # ════════════════════════════════════════════════
        if user_text.lower() in ["دعاء", "ادعية", "ادعيه"]:
            dua = random.choice(DUAS)
            msg = f"🤲 *دعاء*\n\n{dua}\n\n━━━━━━━━━━━\nآمين يا رب العالمين"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 📿 حديث شريف
        # ════════════════════════════════════════════════
        if user_text.lower() in ["حديث", "احاديث", "احاديث شريفة"]:
            hadith = random.choice(HADITHS)
            msg = f"📿 *حديث شريف*\n\n{hadith}\n\n━━━━━━━━━━━\nصدق رسول الله ﷺ"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 📊 الإحصائيات
        # ════════════════════════════════════════════════
        if user_text.lower() in ["إحصائياتي", "احصائياتي", "تقريري", "إحصائيات"]:
            stats = db.get_statistics(target_id, days=7)
            
            msg = "📊 *إحصائياتك الأسبوعية*\n\n"
            
            # إحصائيات التسبيح
            if stats['tasbih']:
                msg += "📿 *التسبيح:*\n"
                for tasbih_type, count in stats['tasbih'].items():
                    msg += f"• {tasbih_type}: {count}\n"
                msg += "\n"
            
            # إحصائيات الأذكار
            if stats['athkar']:
                msg += "🌙 *الأذكار المستلمة:*\n"
                athkar_names = {
                    'morning': 'الصباح',
                    'evening': 'المساء',
                    'sleep': 'النوم'
                }
                for athkar_type, count in stats['athkar'].items():
                    name = athkar_names.get(athkar_type, athkar_type)
                    msg += f"• {name}: {count}\n"
                msg += "\n"
            
            # تقدم القرآن
            quran_progress = get_quran_progress(target_id)
            msg += f"📖 *القرآن الكريم:*\n"
            msg += f"• الأجزاء المكتملة: {quran_progress['completed_juz']}/30\n\n"
            
            msg += "━━━━━━━━━━━\n"
            msg += "✨ بارك الله فيك وزادك من فضله"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 📿 عرض التسبيح
        # ════════════════════════════════════════════════
        if user_text.lower() in ["تسبيح", "عداد", "التسبيح"]:
            progress_text = get_tasbih_progress_text(target_id, today)
            
            msg = f"📿 *تقدم التسبيح اليومي*\n\n{progress_text}\n\n"
            msg += "━━━━━━━━━━━\n"
            
            if check_tasbih_completion(target_id, today):
                msg += "🎉 ماشاء الله! اكتملت جميع الأذكار!"
            else:
                msg += "💪 واصل بارك الله فيك"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        
        # ════════════════════════════════════════════════
        # 🔄 إعادة التسبيح
        # ════════════════════════════════════════════════
        if user_text.lower() in ["إعادة", "reset", "اعادة", "مسح"]:
            db.reset_tasbih(target_id, today)
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ تم إعادة تعيين عداد التسبيح\n\nابدأ من جديد بإذن الله 💚")
            )
            return
        
        # ════════════════════════════════════════════════
        # 📿 معالجة التسبيح
        # ════════════════════════════════════════════════
        clean_text = user_text.replace(" ", "")
        tasbih_map = {
            "سبحانالله": "سبحان الله",
            "الحمدلله": "الحمد لله",
            "اللهأكبر": "الله أكبر",
            "استغفرالله": "استغفر الله",
            "لااللهالاالله": "لا إله إلا الله",
            "لااللهإلاالله": "لا إله إلا الله"
        }
        
        tasbih_type = tasbih_map.get(clean_text)
        
        if tasbih_type:
            count = db.increment_tasbih(target_id, tasbih_type, today)
            
            # رسالة بعد كل تسبيحة
            if count == TASBIH_LIMIT:
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=f"✨ ماشاء الله!\nاكتمل {tasbih_type} (33 مرة)! 🎉")
                )
            
            # عرض التقدم
            progress_text = get_tasbih_progress_text(target_id, today)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"📿 *التسبيح*\n\n{progress_text}")
            )
            
            # التحقق من اكتمال الكل
            if check_tasbih_completion(target_id, today):
                time.sleep(1)
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text="🎉🎉🎉\n\n*ماشاء الله تبارك الله!*\n\nاكتملت جميع الأذكار اليومية!\n\nجزاك الله خيراً وجعلها في ميزان حسناتك\nوجعل الله لك ولوالديك الفردوس الأعلى 💚")
                )
            
            return
        
        # ════════════════════════════════════════════════
        # 📣 ذكرني (للجميع)
        # ════════════════════════════════════════════════
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
            
            # إرسال للجميع
            users = db.get_all_active_users()
            groups = db.get_all_active_groups()
            
            success, failed = send_bulk_messages(users + groups, message, delay=0.8)
            
            # تأكيد للمرسل
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"📣 *تم إرسال التذكير للجميع*\n\n{content}\n\n━━━━━━━━━━━\n✅ نجح: {success}\n❌ فشل: {failed}")
            )
            return
        
        # ════════════════════════════════════════════════
        # ⏸️ إيقاف التنبيهات
        # ════════════════════════════════════════════════
        if user_text.lower() in ["إيقاف", "stop", "ايقاف", "توقف"]:
            db.toggle_notifications(target_id, False, is_group)
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⏸️ *تم إيقاف التذكير التلقائي*\n\nلن تصلك الأذكار التلقائية\n\n💡 لتشغيلها مرة أخرى اكتب: *تشغيل*")
            )
            return
        
        # ════════════════════════════════════════════════
        # ▶️ تشغيل التنبيهات
        # ════════════════════════════════════════════════
        if user_text.lower() in ["تشغيل", "start", "بدء", "تفعيل"]:
            db.toggle_notifications(target_id, True, is_group)
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ *تم تشغيل التذكير التلقائي*\n\nستصلك الأذكار التلقائية:\n• الصباح (7:00)\n• المساء (17:00)\n• النوم (22:00)\n\n🌙 بارك الله فيك")
            )
            return
        
        # ════════════════════════════════════════════════
        # 🆕 رسالة ترحيب للمستخدمين الجدد
        # ════════════════════════════════════════════════
        if is_new:
            welcome_text = """🌙 *السلام عليكم ورحمة الله وبركاته*

✨ مرحبًا بك في بوت *ذكّرني v2.0*

━━━━━━━━━━━━━━━━━
📿 *سيساعدك هذا البوت على:*

• ⏰ تذكّر أذكار الصباح والمساء والنوم
• 📿 متابعة التسبيح اليومي
• 🕌 تنبيهات أوقات الصلاة
• 📖 متابعة قراءة القرآن الكريم
• 🤲 الحصول على أدعية وآيات قرآنية
• 📊 إحصائيات ومتابعة تقدمك

━━━━━━━━━━━━━━━━━
🔹 اكتب *مساعدة* لعرض جميع الأوامر

🤲 جزاك الله خيرًا ونفع بك"""
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=welcome_text)
            )
        
    except Exception as e:
        logger.error(f"⚠️ خطأ في معالجة الرسالة: {e}", exc_info=True)
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ عذراً، حدث خطأ في معالجة طلبك\nالرجاء المحاولة مرة أخرى")
            )
        except:
            pass

# ═══════════════════════════════════════════════════════════
# 🚀 تشغيل جميع الأنظمة
# ═══════════════════════════════════════════════════════════

def start_all_threads():
    """تشغيل جميع الخيوط الخلفية"""
    threads = [
        threading.Thread(target=check_prayer_times, daemon=True, name="PrayerTimes"),
        threading.Thread(target=daily_scheduler, daemon=True, name="DailyAthkar"),
        threading.Thread(target=random_reminders_scheduler, daemon=True, name="RandomReminders"),
        threading.Thread(target=maintenance_tasks, daemon=True, name="Maintenance")
    ]
    
    for thread in threads:
        thread.start()
        logger.info(f"✅ تم تشغيل: {thread.name}")

# ═══════════════════════════════════════════════════════════
# 🎯 نقطة البداية
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔═══════════════════════════════════════╗")
    print("║   🕌 بوت ذكرني الإسلامي v2.0   ║")
    print("╚═══════════════════════════════════════╝")
    print()
    print(f"🗄️  قاعدة البيانات: {DATABASE_PATH}")
    print(f"🚀 المنفذ: {PORT}")
    print(f"🕐 التوقيت: UTC+3 (السعودية)")
    print(f"⏰ الوقت الحالي: {get_current_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # الحصول على الإحصائيات
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM groups")
        group_count = cursor.fetchone()['count']
    
    print(f"👥 المستخدمين: {user_count}")
    print(f"👥 المجموعات: {group_count}")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("🔄 تشغيل الأنظمة الخلفية...")
    
    # تشغيل جميع الخيوط
    start_all_threads()
    
    print()
    print("✅ البوت يعمل الآن بنجاح!")
    print("📝 يتم تسجيل المستخدمين تلقائياً")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # تشغيل Flask
    app.run(host="0.0.0.0", port=PORT, debug=False)
