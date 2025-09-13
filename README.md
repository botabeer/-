# 📖 LINE Islamic Bot

بوت LINE للأدعية والأذكار والقرآن الكريم.

## 🚀 التشغيل
1. انسخ `.env.example` إلى `.env` وضع القيم:
   - LINE_CHANNEL_ACCESS_TOKEN
   - LINE_CHANNEL_SECRET
2. ثبّت المكتبات:
   ```bash
   pip install -r requirements.txt
   ```
3. شغل البوت محليًا:
   ```bash
   python app.py
   ```
4. للنشر على Heroku:
   ```bash
   git init
   git add .
   git commit -m "first commit"
   heroku create
   git push heroku main
   ```

## 🕌 الأوامر
- اذكار الصباح / اذكار المساء
- دعاء بعد الصلاة / دعاء النوم / دعاء الاستيقاظ
- دعاء الجمعة / دعاء السفر / دعاء دخول المسجد / دعاء الخروج من المنزل
- سورة الفاتحة / سورة الكهف / سورة الملك
- آية اليوم / حديث اليوم / حكمة اليوم
- التسبيح (سبحان الله / الحمد لله / الله أكبر)
- مساعدة / تشغيل / ايقاف
