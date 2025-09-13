بوت ذكرني
========

الملفات:
- app.py : كود البوت
- .env : ضع هنا مفاتيح LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET
- requirements.txt : مكتبات بايثون المطلوبة

تشغيل محلي:
1) ثبت المكتبات:
   pip install -r requirements.txt
2) ضع القيم في ملف .env
3) شغّل:
   gunicorn app:app
