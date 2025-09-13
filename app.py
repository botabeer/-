    from flask import Flask, request, abort
    from linebot import LineBotApi, WebhookHandler
    from linebot.exceptions import InvalidSignatureError
    from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
    import os, random, atexit
    from apscheduler.schedulers.background import BackgroundScheduler

    app = Flask(__name__)

    from dotenv import load_dotenv
    load_dotenv()

    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)

    broadcast_active = False
    tasbih_count = {}

    # ---------------- الأذكار والأدعية كاملة ----------------
    adhkar = {
        "اذكار الصباح": """☀️ أذكار الصباح:
أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير. رب أسألك خير ما في هذا اليوم وخير ما بعده، وأعوذ بك من شر ما في هذا اليوم وشر ما بعده، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.

اللهم بك أصبحنا، وبك أمسينا، وبك نحيا، وبك نموت، وإليك النشور.

أعوذ بكلمات الله التامات من شر ما خلق (3 مرات).

بسم الله الذي لا يضر مع اسمه شيء في الأرض ولا في السماء وهو السميع العليم (3 مرات).

اللهم إني أصبحت أشهدك وأشهد حملة عرشك وملائكتك وجميع خلقك أنك أنت الله لا إله إلا أنت وحدك لا شريك لك وأن محمداً عبدك ورسولك (4 مرات).

حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم (7 مرات).

آية الكرسي + المعوذات (الإخلاص، الفلق، الناس 3 مرات).""",

        "اذكار المساء": """🌙 أذكار المساء:
أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير. رب أسألك خير ما في هذه الليلة وخير ما بعدها، وأعوذ بك من شر ما في هذه الليلة وشر ما بعدها، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.

اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير.

أعوذ بكلمات الله التامات من شر ما خلق (3 مرات).

بسم الله الذي لا يضر مع اسمه شيء في الأرض ولا في السماء وهو السميع العليم (3 مرات).

اللهم إني أمسيت أشهدك وأشهد حملة عرشك وملائكتك وجميع خلقك أنك أنت الله لا إله إلا أنت وحدك لا شريك لك وأن محمداً عبدك ورسولك (4 مرات).

حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم (7 مرات).

آية الكرسي + المعوذات (الإخلاص، الفلق، الناس 3 مرات).""",

        "دعاء بعد الصلاة": """🕌 دعاء بعد الصلاة:
أستغفر الله (3 مرات).
اللهم أنت السلام ومنك السلام تباركت يا ذا الجلال والإكرام.

لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير، اللهم لا مانع لما أعطيت ولا معطي لما منعت ولا ينفع ذا الجد منك الجد.

التسبيح: 33 سبحان الله + 33 الحمد لله + 33 الله أكبر + تمام المائة: لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير.""",

        "دعاء النوم": """🌙 دعاء النوم:
باسمك ربي وضعت جنبي وبك أرفعه، إن أمسكت نفسي فارحمها وإن أرسلتها فاحفظها بما تحفظ به عبادك الصالحين.

قراءة: آية الكرسي.
قراءة: المعوذات (الإخلاص، الفلق، الناس) 3 مرات.

سبحان الله 33، الحمد لله 33، الله أكبر 34.""",

        "دعاء الاستيقاظ": """🌅 دعاء الاستيقاظ:
الحمد لله الذي أحيانا بعدما أماتنا وإليه النشور.

لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير، سبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر، ولا حول ولا قوة إلا بالله العلي العظيم.""",

        "دعاء الجمعة": "اللهم اجعلنا من المقبولين في يوم الجمعة، اللهم اغفر لنا ما قدمنا وما أخرنا وما أسررنا وما أعلنا.",
        "دعاء السفر": "اللهم إنا نسألك في سفرنا هذا البر والتقوى ومن العمل ما ترضى، اللهم هون علينا سفرنا هذا واطوِ عنا بعده، اللهم أنت الصاحب في السفر والخليفة في الأهل.",
        "دعاء دخول المسجد": "اللهم افتح لي أبواب رحمتك.",
        "دعاء الخروج من المسجد": "اللهم إني أسألك من فضلك.",
        "دعاء الخروج من المنزل": "بسم الله، توكلت على الله، ولا حول ولا قوة إلا بالله.",
        "دعاء الكرب": "لا إله إلا الله العظيم الحليم، لا إله إلا الله رب العرش العظيم، لا إله إلا الله رب السماوات ورب الأرض ورب العرش الكريم.",
        "دعاء الاستخارة": "اللهم إني استخيرك بعلمك، وأستقدرك بقدرتك، وأسألك من فضلك العظيم، فإنك تقدر ولا أقدر وتعلم ولا أعلم وأنت علام الغيوب...",
        "دعاء الرزق": "اللهم ارزقني رزقاً حلالاً طيباً واسعاً مباركاً فيه."
    }

    quran = {
        "سورة الفاتحة": "بسم الله الرحمن الرحيم. الحمد لله رب العالمين * الرحمن الرحيم * مالك يوم الدين * إياك نعبد وإياك نستعين * اهدنا الصراط المستقيم * صراط الذين أنعمت عليهم غير المغضوب عليهم ولا الضالين.",
        "سورة الكهف": "الحمد لله الذي أنزل على عبده الكتاب ولم يجعل له عوجا... (السورة كاملة تقرأ يوم الجمعة).",
        "سورة الملك": "تبارك الذي بيده الملك وهو على كل شيء قدير... (السورة كاملة).",
        "آية الكرسي": "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ... (البقرة: 255)",
        "المعوذات": "قُلْ هُوَ اللَّهُ أَحَدٌ * اللَّهُ الصَّمَدُ * لَمْ يَلِدْ وَلَمْ يُولَدْ * وَلَمْ يَكُن لَّهُ كُفُوًا أَحَدٌ. قُلْ أَعُوذُ بِرَبِّ الْفَلَقِ... قُلْ أَعُوذُ بِرَبِّ النَّاسِ..."
    }

    ayat = [
        "وَقُل رَّبِّ زِدْنِي عِلْمًا",
        "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
        "فاذكروني أذكركم",
        "اللَّهُ وَلِيُّ الَّذِينَ آمَنُوا"
    ]

    ahadith = [
        "قال النبي ﷺ: خيركم من تعلم القرآن وعلمه",
        "قال النبي ﷺ: الكلمة الطيبة صدقة",
        "قال النبي ﷺ: من سلك طريقًا يلتمس فيه علمًا سهّل الله له به طريقًا إلى الجنة",
        "قال النبي ﷺ: لا تحقرن من المعروف شيئًا"
    ]

    hikmah = [
        "من جد وجد ومن زرع حصد",
        "العلم نور يهدي إلى الحق",
        "النية الصالحة تحول العادة إلى عبادة"
    ]

    # ---------------- النشر التلقائي ----------------
    scheduler = BackgroundScheduler()

    def send_morning_broadcast():
        if not broadcast_active:
            return
        text = adhkar["اذكار الصباح"] + "\n\n📖 آية اليوم:\n" + random.choice(ayat)
        try:
            line_bot_api.broadcast(TextSendMessage(text=text))
        except Exception as e:
            print("Error broadcasting morning:", e)

    def send_evening_broadcast():
        if not broadcast_active:
            return
        text = adhkar["اذكار المساء"] + "\n\n📜 حديث اليوم:\n" + random.choice(ahadith)
        try:
            line_bot_api.broadcast(TextSendMessage(text=text))
        except Exception as e:
            print("Error broadcasting evening:", e)

    scheduler.add_job(send_morning_broadcast, "cron", hour=7, minute=0)
    scheduler.add_job(send_evening_broadcast, "cron", hour=19, minute=0)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    WELCOME_TEXT = (
        "👋 أهلاً بك في بوت الأذكار والقرآن 📖\n\n"
        "🌟 الأوامر:\n"
        "- اذكار الصباح / اذكار المساء / دعاء النوم / دعاء الاستيقاظ / دعاء بعد الصلاة\n"
        "- دعاء الجمعة / دعاء السفر / دعاء دخول المسجد / دعاء الخروج من المسجد / دعاء الخروج من المنزل\n"
        "- دعاء الكرب / دعاء الاستخارة / دعاء الرزق\n"
        "- سورة الفاتحة / سورة الكهف / سورة الملك / آية الكرسي / المعوذات\n"
        "- آية اليوم / حديث اليوم / حكمة اليوم\n"
        "- التسبيح: سبحان الله / الحمد لله / الله أكبر\n"
        "- تشغيل (تفعيل النشر) / ايقاف / مساعدة"
    )

    @handler.add(FollowEvent)
    def handle_follow(event):
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=WELCOME_TEXT))
        except Exception as e:
            print("FollowEvent error:", e)

    @app.route("/callback", methods=["POST"])
    def callback():
        signature = request.headers.get("X-Line-Signature", "")
        body = request.get_data(as_text=True)
        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            abort(400)
        return "OK"

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        global broadcast_active, tasbih_count
        text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)

        if text == "ايقاف":
            broadcast_active = False
            reply = "🚫 تم إيقاف النشر التلقائي."
        elif text in ["تشغيل", "تفعيل"]:
            broadcast_active = True
            reply = "✅ تم تفعيل النشر التلقائي (أذكار الصباح 7:00، المساء 19:00)."
        elif text == "مساعدة":
            reply = WELCOME_TEXT
        elif text in adhkar:
            reply = adhkar[text]
        elif text in quran:
            reply = quran[text]
        elif text == "آية اليوم":
            reply = random.choice(ayat)
        elif text == "حديث اليوم":
            reply = random.choice(ahadith)
        elif text == "حكمة اليوم":
            reply = random.choice(hikmah)
        elif text in ["سبحان الله", "الحمد لله", "الله أكبر"]:
            if user_id:
                tasbih_count.setdefault(user_id, 0)
                tasbih_count[user_id] += 1
                reply = f"{text} ({tasbih_count[user_id]})"
            else:
                reply = text
        else:
            reply = "❓ لم أفهم الأمر. اكتب (مساعدة) لعرض الأوامر."

        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        except Exception as e:
            print("reply error:", e)

    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
