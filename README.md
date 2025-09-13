LINE Islamic Bot - Full Adhkar Version

شغل البوت:
1. ضع متغيرات البيئة في ملف .env أو في إعدادات Render/Heroku:
   LINE_CHANNEL_ACCESS_TOKEN
   LINE_CHANNEL_SECRET
2. ثبت المتطلبات:
   pip install -r requirements.txt
3. شغل التطبيق:
   gunicorn app:app
