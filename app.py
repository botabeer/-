# إضافة هذا أعلى الكود قبل استخدامه
links_count = {}  # عداد الروابط لكل مستخدم

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global auto_reminder_enabled
    user_id = event.source.user_id
    text = event.message.text.strip()

    # الروابط المكررة — وضعها في البداية أو بعد أوامر محددة
    if "http" in text or "https" in text:
        if user_id not in links_count:
            links_count[user_id] = 1  # أول رابط
        else:
            if links_count[user_id] == 1:  # إذا هذه المرة الثانية
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="الرجاء عدم تكرار الروابط")
                )
            links_count[user_id] = 2  # بعد التحذير، الثبات على 2 لتجنب التكرار
        return

    # أوامر محددة فقط — يتجاهل أي نص آخر
    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return
    if text == "صباح":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_SABAH))
        return
    if text == "مساء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_MASAA))
        return
    if text == "نوم":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AZKAR_NAWM))
        return
    if text == "آية":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=AYAT_KURSI))
        return
    if text == "دعاء":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(DUA_LIST)))
        return
    if text == "حديث":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(HADITH_LIST)))
        return
    if text == "تشغيل":
        subscribers.add(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم تفعيل التذكير التلقائي"))
        return
    if text == "إيقاف":
        subscribers.discard(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إيقاف التذكير التلقائي"))
        return
    # تسبيح: بدء أو زيادة حسب العبارة
    if text == "تسبيح":
        ensure_user_counts(user_id)
        counts = tasbih_counts[user_id]
        status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        return
    if text in ("سبحان الله", "الحمد لله", "الله أكبر"):
        ensure_user_counts(user_id)
        if tasbih_counts[user_id][text] < tasbih_limits:
            tasbih_counts[user_id][text] += 1
            if tasbih_counts[user_id][text] >= tasbih_limits:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اكتمل {text} ({tasbih_limits} مرة)"))
            else:
                counts = tasbih_counts[user_id]
                status = f"سبحان الله: {counts['سبحان الله']}/33\nالحمد لله: {counts['الحمد لله']}/33\nالله أكبر: {counts['الله أكبر']}/33"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{text} مكتمل ({tasbih_limits} مرة)"))
        return

    # أي نص آخر نتجاهله (لا نرد)
    return
