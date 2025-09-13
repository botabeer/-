\
    from flask import Flask, request, abort
    from linebot import LineBotApi, WebhookHandler
    from linebot.exceptions import InvalidSignatureError
    from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent, JoinEvent
    from apscheduler.schedulers.background import BackgroundScheduler
    from dotenv import load_dotenv
    import os, random, time

    # load env
    load_dotenv()
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

    app = Flask(__name__)
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN) if LINE_CHANNEL_ACCESS_TOKEN else None
    handler = WebhookHandler(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None

    # Subscribers who enabled auto (user_id / group_id / room_id)
    subscribers = set()
    # tasbih counters per sender_id
    tasbih_counters = {}
    # whether auto sending is globally enabled (but individual subscription controls actual recipients)
    auto_enabled = True

    # delay between messages (seconds)
    MESSAGE_DELAY = 2

    # --- Full texts --- (no emojis, no symbols)
    ADHKAR_SABAH = [
    \"\"\"أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير.
    ربِّ أسألك خير ما في هذا اليوم وخير ما بعده، وأعوذ بك من شر ما في هذا اليوم وشر ما بعده، ربِّ أعوذ بك من الكسل وسوء الكِبَر،
    ربِّ أعوذ بك من عذاب في النار وعذاب في القبر.\"\"\",

    \"\"\"اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور.\"\"\",

    \"\"\"اللهم أنت ربي لا إله إلا أنت خلقتني وأنا عبدك وأنا على عهدك ووعدك ما استطعت أعوذ بك من شر ما صنعت أبوء لك بنعمتك علي وأبوء بذنبي فاغفر لي فإنه لا يغفر الذنوب إلا أنت.\"\"\",

    \"\"\"رضيت بالله ربًا وبالإسلام دينًا وبمحمد صلى الله عليه وسلم نبيًا ورسولًا.\"\"\",

    \"\"\"اللهم ما أصبح بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك فلك الحمد ولك الشكر.\"\"\",

    \"\"\"حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم.\"\"\",

    \"\"\"بِسْمِ اللهِ الَّذِي لا يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الْأَرْضِ وَلَا فِي السَّمَاءِ وَهُوَ السَّمِيعُ العَلِيمُ.\"\"",
    ]

    ADHKAR_MASA = [
    \"\"\"أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير.
    ربِّ أسألك خير ما في هذه الليلة وخير ما بعدها، وأعوذ بك من شر ما في هذه الليلة وشر ما بعدها، ربِّ أعوذ بك من الكسل وسوء الكِبَر,
    ربِّ أعوذ بك من عذاب في النار وعذاب في القبر.\"\"\",

    \"\"\"اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير.\"\"\",

    \"\"\"اللهم إني أمسيت أشهدك وأشهد حملة عرشك وملائكتك وجميع خلقك أنك أنت الله لا إله إلا أنت وحدك لا شريك لك وأن محمداً عبدك ورسولك.\"\"\",

    \"\"\"رضيت بالله ربًا وبالإسلام دينًا وبمحمد صلى الله عليه وسلم نبيًا ورسولًا.\"\"\",

    \"\"\"اللهم ما أمسى بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك فلك الحمد ولك الشكر.\"\"\",

    \"\"\"حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم.\"\"",
    ]

    ADHKAR_NAWM = [
    \"\"\"باسمك ربي وضعت جنبي وبك أرفعه إن أمْسَكت نفسي فارحمها وإن أرسلتها فاحفظها بما تحفظ به عبادك الصالحين.\"\"\",
    \"\"\"اللهم باسمك أموت وأحيا.\"\"\",
    \"\"\"اللهم قِني عذابك يوم تبعث عبادك.\"\"\",
    \"\"\"اللهم أسلمت نفسي إليك وفوضت أمري إليك ووجهت وجهي إليك وألجأت ظهري إليك رغبة ورهبة إليك لا ملجأ ولا منجى منك إلا إليك.\"\"\",
    \"سبحان الله (33 مرة)\",\n    \"الحمد لله (33 مرة)\",\n    \"الله أكبر (34 مرة)\"\n    ]

    # Qur'an texts (full-like)
    SURAH_AL_FATIHA = (\n        \"بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ\\n\"
    \"الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ\\n\"
    \"الرَّحْمَٰنِ الرَّحِيمِ\\n\"
    \"مَالِكِ يَوْمِ الدِّينِ\\n\"
    \"إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ\\n\"
    \"اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ\\n\"
    \"صِرَاطَ الَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ الْمَغْضُوبِ عَلَيْهِمْ وَلَا الضَّالِّينِ\")\n\n    AYAT_KURSI = (\n        \"اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ ۚ لَا تَأْخُذُهُ سِنَةٌ وَلَا نَوْمٌ ۚ \\n\"\n        \"لَهُ مَا فِي السَّمَاوَاتِ وَمَا فِي الْأَرْضِ ۗ مَنْ ذَا الَّذِي يَشْفَعُ عِنْدَهُ إِلَّا بِإِذْنِهِ ۚ\\n\"\n        \"يَعْلَمُ مَا بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ ۖ وَلَا يُحِيطُونَ بِشَيْءٍ مِّنْ عِلْمِهِ إِلَّا بِمَا شَاءَ ۚ\\n\"\n        \"وَسِعَ كُرْسِيُّهُ السَّمَاوَاتِ وَالْأَرْضَ ۗ وَلَا يَئُودُهُ حِفْظُهُمَا ۚ وَهُوَ الْعَلِيُّ الْعَظِيمُ\")\n\n    LAST_TWO_BAQARA = (\n        \"آمَنَ الرَّسُولُ بِمَا أُنزِلَ إِلَيْهِ مِن رَّبِّهِ وَالْمُؤْمِنُونَ ۚ كُلٌّ آمَنَ بِاللَّهِ وَمَلَائِكَتِهِ وَكُتُبِهِ وَرُسُلِهِ لَا نُفَرِّقُ بَيْنَ أَحَدٍ مِّن رُّسُلِهِ ۚ \\n\"\n        \"وَقَالُوا سَمِعْنَا وَأَطَعْنَا ۖ غُفْرَانَكَ رَبَّنَا وَإِلَيْكَ الْمَصِيرُ \\n\"\n        \"لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا ۚ لَهَا مَا كَسَبَتْ وَعَلَيْهَا مَا اكْتَسَبَتْ ۗ \\n\"\n        \"رَبَّنَا لَا تُؤَاخِذْنَا إِن نَّسِينَا أَوْ أَخْطَأْنَا \\n\"\n        \"رَبَّنَا وَلَا تَحْمِلْ عَلَيْنَا إِصْرًا كَمَا حَمَلْتَهُ عَلَى الَّذِينَ مِن قَبْلِنَا \\n\"\n        \"رَبَّنَا وَلَا تُحَمِّلْنَا مَا لَا طَاقَةَ لَنَا بِهِ وَاعْفُ عَنَّا وَاغْفِرْ لَنَا وَارْحَمْنَا \\n\"\n        \"أَنتَ مَوْلَانَا فَانصُرْنَا عَلَى الْقَوْمِ الْكَافِرِينَ\")\n\n    SURAH_IKHLAS = \"قُلْ هُوَ اللَّهُ أَحَدٌ\\nاللَّهُ الصَّمَدُ\\nلَمْ يَلِدْ وَلَمْ يُولَدْ\\nوَلَمْ يَكُن لَّهُ كُفُوًا أَحَدٌ\"\n    SURAH_AL_FALAQ = \"قُلْ أَعُوذُ بِرَبِّ الْفَلَقِ\\nمِن شَرِّ مَا خَلَقَ\\nوَمِن شَرِّ غَاسِقٍ إِذَا وَقَبَ\\nوَمِن شَرِّ النَّفَّاثَاتِ فِي الْعُقَدِ\\nوَمِن شَرِّ حَاسِدٍ إِذَا حَسَدَ\"\n    SURAH_AN_NAS = \"قُلْ أَعُوذُ بِرَبِّ النَّاسِ\\nمَلِكِ النَّاسِ\\nإِلَٰهِ النَّاسِ\\nمِن شَرِّ الْوَسْوَاسِ الْخَنَّاسِ\\nالَّذِي يُوَسْوِسُ فِي صُدُورِ النَّاسِ\\nمِنَ الْجِنَّةِ وَالنَّاسِ\"\n\n    # pools for duas and hadiths\n    DUA_POOL = [\n    \"اللهم آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار.\",\n    \"اللهم اغفر لي ولوالدي وارحمهما كما ربياني صغيرًا.\",\n    \"اللهم ثبتنا على الحق وارزقنا عملًا صالحًا يقربنا إليك.\"\n    ]\n\n    HADITH_POOL = [\n    \"عن النبي صلى الله عليه وسلم: من قال سبحان الله وبحمده مائة مرة غفرت خطاياه.\",\n    \"عن النبي صلى الله عليه وسلم: الكلمة الطيبة صدقة.\",\n    \"عن النبي صلى الله عليه وسلم: تبسمك في وجه أخيك صدقة.\"\n    ]\n\n    # helper: add subscriber id from event.source\n    def extract_sender_id(source):\n        # prefer group_id/room_id to send to group when in group\n        gid = getattr(source, 'group_id', None)\n        if gid:\n            return gid\n        rid = getattr(source, 'room_id', None)\n        if rid:\n            return rid\n        return getattr(source, 'user_id', None)\n\n    def send_list_as_separate(recipient_id, items):\n        if not line_bot_api:\n            return\n        for item in items:\n            try:\n                line_bot_api.push_message(recipient_id, TextSendMessage(text=item))\n            except Exception as e:\n                print('push error', e)\n            time.sleep(MESSAGE_DELAY)\n\n    # webhook\n    @app.route('/callback', methods=['POST'])\n    def callback():\n        signature = request.headers.get('X-Line-Signature', '')\n        body = request.get_data(as_text=True)\n        try:\n            handler.handle(body, signature)\n        except InvalidSignatureError:\n            abort(400)\n        return 'OK'\n\n    @handler.add(FollowEvent)\n    def on_follow(event):\n        # send short welcome in private follow\n        if line_bot_api:\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='مرحباً بك في بوت ذكرني\\nاكتب مساعدة لعرض الأوامر'))\n\n    @handler.add(JoinEvent)\n    def on_join(event):\n        # when added to group\n        if line_bot_api:\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='تمت إضافتي للمجموعة. اكتب مساعدة لعرض الأوامر'))\n\n    @handler.add(MessageEvent, message=TextMessage)\n    def handle_message(event):\n        global auto_enabled\n        text = event.message.text.strip()\n        sender_id = extract_sender_id(event.source)\n\n        # respond only to defined commands\n        if text in ['مساعدة', 'help']:\n            help_text = (\n                'الأوامر:\\n'\n                'صباح - أذكار الصباح\\n'\n                'مساء - أذكار المساء\\n'\n                'نوم - أذكار النوم\\n'\n                'دعاء - يعرض دعاء\\n'\n                'حديث - يعرض حديث\\n'\n                'آية - يعرض آية/سورة\\n'\n                'عداد - عداد تسبيح\\n'\n                'تشغيل - تفعيل التذكير التلقائي\\n'\n                'إيقاف - إيقاف التذكير التلقائي'\n            )\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))\n            return\n\n        if text == 'تشغيل':\n            if sender_id:\n                subscribers.add(sender_id)\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='تم تفعيل الإرسال التلقائي.'))\n            return\n\n        if text == 'إيقاف':\n            if sender_id and sender_id in subscribers:\n                subscribers.discard(sender_id)\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='تم إيقاف الإرسال التلقائي.\\nلن تستقبل التنبيهات إلا إذا أعدت تشغيل البوت.'))\n            return\n\n        if text == 'صباح':\n            # send each adhkar as separate message\n            send_list_as_separate(sender_id, ADHKAR_SABAH)\n            return\n\n        if text == 'مساء':\n            send_list_as_separate(sender_id, ADHKAR_MASA)\n            return\n\n        if text == 'نوم':\n            items = ADHKAR_NAWM + [SURAH_AL_FATIHA, AYAT_KURSI, LAST_TWO_BAQARA, SURAH_IKHLAS, SURAH_AL_FALAQ, SURAH_AN_NAS]\n            send_list_as_separate(sender_id, items)\n            return\n\n        if text == 'دعاء':\n            picks = random.sample(DUA_POOL, min(3, len(DUA_POOL)))\n            send_list_as_separate(sender_id, picks)\n            return\n\n        if text == 'حديث':\n            send_list_as_separate(sender_id, [random.choice(HADITH_POOL)])\n            return\n\n        if text == 'آية':\n            picks = [SURAH_AL_FATIHA, AYAT_KURSI, LAST_TWO_BAQARA, SURAH_IKHLAS, SURAH_AL_FALAQ, SURAH_AN_NAS]\n            send_list_as_separate(sender_id, [random.choice(picks)])\n            return\n\n        if text == 'عداد':\n            if not sender_id:\n                line_bot_api.reply_message(event.reply_token, TextSendMessage(text='لا يمكن تتبع العداد في هذا السياق.'))\n                return\n            tasbih_counters[sender_id] = {'سبحان الله':0, 'الحمد لله':0, 'الله أكبر':0}\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='ابدأ بالتسبيح. اكتب سبحان الله أو الحمد لله أو الله أكبر لزيادة العداد. اكتب انتهيت عند الانتهاء.'))\n            return\n\n        if text in ['سبحان الله', 'الحمد لله', 'الله أكبر']:\n            if not sender_id or sender_id not in tasbih_counters:\n                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=\"اكتب 'عداد' لبدء عداد التسبيح أولاً.\"))\n                return\n            tasbih_counters[sender_id][text] = tasbih_counters[sender_id].get(text,0) + 1\n            status = (\n                f\"سبحان الله ({tasbih_counters[sender_id]['سبحان الله']})\\n\"\n                f\"الحمد لله ({tasbih_counters[sender_id]['الحمد لله']})\\n\"\n                f\"الله أكبر ({tasbih_counters[sender_id]['الله أكبر']})\"\n            )\n            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=status))\n            # completion check\n            c = tasbih_counters[sender_id]\n            if c['سبحان الله'] >= 33 and c['الحمد لله'] >= 33 and c['الله أكبر'] >= 33:\n                line_bot_api.push_message(sender_id, TextSendMessage(text='أكملت التسبيح، ما شاء الله.'))\n                tasbih_counters.pop(sender_id, None)\n            return\n\n        if text == 'انتهيت':\n            if sender_id and sender_id in tasbih_counters:\n                tasbih_counters.pop(sender_id, None)\n                line_bot_api.reply_message(event.reply_token, TextSendMessage(text='تم إنهاء جلسة التسبيح.'))\n            return\n\n        # otherwise ignore (no reply)\n        return\n\n    # --- Scheduled sending ---\n    scheduler = BackgroundScheduler()\n\n    def send_daily_sabah():\n        if not auto_enabled:\n            return\n        for recip in list(subscribers):\n            send_list_as_separate(recip, ADHKAR_SABAH)\n\n    def send_daily_masaa():\n        if not auto_enabled:\n            return\n        for recip in list(subscribers):\n            send_list_as_separate(recip, ADHKAR_MASA)\n\n    def send_daily_nawm():\n        if not auto_enabled:\n            return\n        for recip in list(subscribers):\n            send_list_as_separate(recip, ADHKAR_NAWM + [SURAH_AL_FATIHA, AYAT_KURSI, LAST_TWO_BAQARA, SURAH_IKHLAS, SURAH_AL_FALAQ, SURAH_AN_NAS])\n\n    def send_random_trip():\n        if not auto_enabled:\n            return\n        pool = ADHKAR_SABAH + ADHKAR_MASA + ADHKAR_NAWM + DUA_POOL + HADITH_POOL + [SURAH_AL_FATIHA, AYAT_KURSI]\n        for recip in list(subscribers):\n            picks = random.sample(pool, min(3, len(pool)))\n            send_list_as_separate(recip, picks)\n\n    # schedule: sabah 4:00, masaa 16:00 (4 عصر), nawm 22:00\n    scheduler.add_job(send_daily_sabah, 'cron', hour=4, minute=0)\n    scheduler.add_job(send_daily_masaa, 'cron', hour=16, minute=0)\n    scheduler.add_job(send_daily_nawm, 'cron', hour=22, minute=0)\n    # 5 times/day ~ every 4 hours\n    scheduler.add_job(send_random_trip, 'interval', hours=4)\n    scheduler.start()\n\n    if __name__ == '__main__':\n        port = int(os.environ.get('PORT', 5000))\n        app.run(host='0.0.0.0', port=port)\n    