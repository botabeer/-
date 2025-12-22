import sqlite3

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

# إنشاء جدول المستخدمين
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    notifications_enabled INTEGER DEFAULT 1,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# إنشاء جدول المجموعات
cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY,
    notifications_enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# إدخال بيانات تجريبية
cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", ("U123456789", "TestUser1"))
cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", ("U987654321", "TestUser2"))
cursor.execute("INSERT OR IGNORE INTO groups (group_id) VALUES (?)", ("G123456789",))
conn.commit()
conn.close()

print("✅ قاعدة البيانات جاهزة مع بيانات تجريبية.")
