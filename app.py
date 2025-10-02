@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # أمر ذكرني: نرسل للمرسل أولاً لتجربة الرد
    if user_text.lower() == "ذكرني":
        category = random.choice(["duas", "adhkar", "hadiths"])
        message = random.choice(content[category])
        try:
            # الرد للمرسل مباشرة أولاً
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"تم: {message}"))
        except:
            print("خطأ في إرسال الرسالة")
