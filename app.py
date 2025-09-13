from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, FollowEvent
import os, random, atexit
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# load adhkar files into lists (each paragraph as one item)
import glob
def load_list(path):
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read().strip()
    # split by double newlines to separate paragraphs/entries
    for part in text.split('\n\n'):
        part = part.strip()
        if part:
            items.append(part)
    return items

adhkar = {}
base = os.path.join(os.path.dirname(__file__), 'adhkar')
mapping = {
    'اذكار الصباح': 'sabah.txt',
    'اذكار المساء': 'masa.txt',
    'اذكار النوم': 'nawm.txt',
    'اذكار بعد الصلاة': 'salah.txt',
    'اذكار الجمعة': 'jummah.txt',
    'دعاء السفر': 'travel.txt',
    'دعاء الكرب': 'karb.txt',
    'دعاء الاستغفار': 'istighfar.txt',
    'دعاء دخول المسجد': 'mosque_in.txt',
    'دعاء الخروج من المسجد': 'mosque_out.txt',
    'دعاء دخول المنزل': 'home_in.txt',
    'دعاء الخروج من المنزل': 'home_out.txt',
    'آيات قصيرة': 'quran.txt',
    'تسبيح': 'tasbeeh.txt',
    'صلاة على النبي': 'salat_nabi.txt'
}

for key, fname in mapping.items():
    path = os.path.join(base, fname)
    if os.path.exists(path):
        adhkar[key] = load_list(path)
    else:
        adhkar[key] = []

# store targets (groups and users) for broadcasting
targets = set()

# scheduler for broadcasts
scheduler = BackgroundScheduler()
broadcast_active = False

def send_book_to_target(target_id, category, index=0, push=False):
    items = adhkar.get(category, [])
    if not items:
        return
    # send intro line then first item or specified index
    intro_map = {
        'اذكار الصباح': 'هذه أذكار الصباح، يمكنك التنقل بينها عبر الأزرار.',
        'اذكار المساء': 'هذه أذكار المساء، يمكنك التنقل بينها عبر الأزرار.',
        'اذكار النوم': 'هذه أذكار النوم، يمكنك التنقل بينها عبر الأزرار.'
    }
    if push:
        try:
            line_bot_api.push_message(target_id, TextSendMessage(text=intro_map.get(category, '')))
        except:
            pass
    else:
        # reply in conversation
        try:
            line_bot_api.reply_message(target_id, TextSendMessage(text=intro_map.get(category, '')))
        except:
            pass

    # send the specified index as a message with quick replies for navigation
    def send_index(to_id, idx, reply_token=None, use_reply=False):
        text = items[idx]
        buttons = []
        if idx > 0:
            buttons.append(QuickReplyButton(action=MessageAction(label='السابق', text=f'{category} {idx-1}')))
        if idx < len(items) - 1:
            buttons.append(QuickReplyButton(action=MessageAction(label='التالي', text=f'{category} {idx+1}')))
        msg = TextSendMessage(text=text, quick_reply=QuickReply(items=buttons) if buttons else None)
        try:
            if use_reply and reply_token:
                line_bot_api.reply_message(reply_token, msg)
            else:
                line_bot_api.push_message(to_id if to_id else reply_token, msg)
        except Exception as e:
            print('send_index error', e)

    # push the first item
    try:
        line_bot_api.push_message(target_id, TextSendMessage(text=items[index], quick_reply=QuickReply(items=[
            QuickReplyButton(action=MessageAction(label='السابق', text=f'{category} {max(0,index-1)}')) if index>0 else None,
            QuickReplyButton(action=MessageAction(label='التالي', text=f'{category} {min(len(items)-1,index+1)}')) if index < len(items)-1 else None
        ])))
    except Exception as e:
        print('push error', e)

# Broadcast jobs
def morning_job():
    if not broadcast_active:
        return
    # send to all targets individually
    for t in list(targets):
        send_book_to_target(t, 'اذكار الصباح', 0, push=True)

def evening_job():
    if not broadcast_active:
        return
    for t in list(targets):
        send_book_to_target(t, 'اذكار المساء', 0, push=True)

def night_job():
    if not broadcast_active:
        return
    for t in list(targets):
        send_book_to_target(t, 'اذكار النوم', 0, push=True)

# schedule: 4:00, 16:00, 22:00
scheduler.add_job(morning_job, 'cron', hour=4, minute=0)
scheduler.add_job(evening_job, 'cron', hour=16, minute=0)
scheduler.add_job(night_job, 'cron', hour=22, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

WELCOME = """السلام عليكم ورحمة الله وبركاته

أنا بوت إسلامي
أساعدك في الأذكار والأدعية والأوقات اليومية

الأوامر المتاحة:
- اذكار الصباح
- اذكار المساء
- اذكار النوم
- اذكار بعد الصلاة
- اذكار يوم الجمعة
- دعاء السفر
- دعاء الكرب
- أدعية الاستغفار
- دعاء دخول المسجد
- دعاء الخروج من المسجد
- دعاء دخول المنزل
- دعاء الخروج من المنزل
- آيات قرآنية قصيرة
- أذكار التسبيح
- الصلاة على النبي صلى الله عليه وسلم

ملاحظة: الأذكار تُرسل تلقائياً
- أذكار الصباح: 4 فجراً
- أذكار المساء: 4 عصراً
- أذكار النوم: 10 مساءً

اكتب أي أمر مثل: اذكار الصباح لعرضها كاملة مع إمكانية التنقل بين الأذكار
"""

@handler.add(FollowEvent)
def on_follow(event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=WELCOME))
    except Exception as e:
        print('follow reply error', e)

@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global broadcast_active
    text = event.message.text.strip()
    # save user/group id to targets for broadcasting
    src = event.source
    target_id = None
    if hasattr(src, 'group_id') and src.group_id:
        target_id = src.group_id
    elif hasattr(src, 'user_id') and src.user_id:
        target_id = src.user_id
    if target_id:
        targets.add(target_id)

    if text == 'مساعدة':
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=WELCOME))
        return
    if text in ['تشغيل الرسائل', 'تشغيل']:
        broadcast_active = True
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='تم تفعيل الإرسال التلقائي'))
        return
    if text in ['ايقاف الرسائل', 'ايقاف']:
        broadcast_active = False
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='تم إيقاف الإرسال التلقائي'))
        return
    # handle book commands and navigation
    for key in adhkar.keys():
        if text == key:
            # send intro then first item as reply
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='هذه ' + key + '، يمكنك التنقل بينها عبر الأزرار.'))
            # send first item
            items = adhkar[key]
            if items:
                # send first item with quick reply buttons
                buttons = []
                if len(items) > 1:
                    buttons = [QuickReplyButton(action=MessageAction(label='السابق', text=f'{key} 0')), QuickReplyButton(action=MessageAction(label='التالي', text=f'{key} 1'))]
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=items[0], quick_reply=QuickReply(items=buttons) if buttons else None))
            return
        # navigation like "اذكار الصباح 3"
        if text.startswith(key + ' '):
            parts = text.split()
            try:
                idx = int(parts[1])
                items = adhkar.get(key, [])
                if 0 <= idx < len(items):
                    buttons = []
                    if idx > 0:
                        buttons.append(QuickReplyButton(action=MessageAction(label='السابق', text=f'{key} {idx-1}')))
                    if idx < len(items)-1:
                        buttons.append(QuickReplyButton(action=MessageAction(label='التالي', text=f'{key} {idx+1}')))
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=items[idx], quick_reply=QuickReply(items=buttons) if buttons else None))
                    return
            except:
                pass
    # if command not matched
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='أمر غير معروف. اكتب مساعدة لمعرفة الأوامر.'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
