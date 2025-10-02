from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
import os, json, random, threading, time
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
PORT = int(os.getenv("PORT",5000))

# بيانات
DATA_FILE, CONTENT_FILE = "data.json","content.json"
data = {"users":[], "groups":[], "tasbih":{}, "notifications_off":[]}
if os.path.exists(DATA_FILE): data.update(json.load(open(DATA_FILE,"r",encoding="utf-8")))
content = json.load(open(CONTENT_FILE,"r",encoding="utf-8"))

users, groups = set(data["users"]), set(data["groups"])
tasbih, notifications_off = data["tasbih"], set(data["notifications_off"])

def save(): json.dump({"users":list(users),"groups":list(groups),"tasbih":tasbih,"notifications_off":list(notifications_off)}, open(DATA_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def ensure_user(uid): tasbih.setdefault(uid,{"سبحان الله":0,"الحمد لله":0,"الله أكبر":0})
def rand_msg(): return random.choice(content[random.choice(["duas","adhkar","hadiths"])])
def send_all(): [line_bot_api.push_message(tid,TextSendMessage(rand_msg())) for tid in list(users)+list(groups) if tid not in notifications_off]

# إرسال تلقائي
def loop(): 
    while True: send_all(); time.sleep(random.randint(3600,5400))
threading.Thread(target=loop,daemon=True).start()

# حماية روابط
links_count = {}
def handle_links(event,uid):
    t = event.message.text.strip()
    if any(x in t for x in ["http://","https://","www."]):
        links_count[uid] = links_count.get(uid,0)+1
        if links_count[uid]>=2: line_bot_api.reply_message(event.reply_token,TextSendMessage("الرجاء عدم تكرار الروابط"))
        return True
    return False

# Webhook
@app.route("/",methods=["GET"])
def home(): return "Bot is running",200

@app.route("/callback",methods=["POST"])
def callback():
    sig=request.headers.get("X-Line-Signature","")
    body=request.get_data(as_text=True)
    try: handler.handle(body,sig)
    except InvalidSignatureError: print("خطأ في التوقيع")
    return "OK",200

# معالجة الرسائل
@handler.add(MessageEvent,message=TextMessage)
def handle(event):
    text = event.message.text.strip()
    uid = event.source.user_id
    gid = getattr(event.source,"group_id",None)
    tid = gid if gid else uid
    first = False

    # تسجيل
    if gid and gid not in groups: first=True; groups.add(gid)
    if not gid and uid not in users: first=True; users.add(uid)
    save(); ensure_user(uid)

    # أول رسالة
    if first and tid not in notifications_off: line_bot_api.push_message(tid,TextSendMessage(rand_msg()))

    if handle_links(event,uid): return

    # أوامر
    if text.lower()=="مساعدة":
        line_bot_api.reply_message(event.reply_token,TextSendMessage("""أوامر البوت المتاحة:

1. ذكرني
   - يرسل دعاء أو حديث أو ذكر عشوائي لجميع المستخدمين.

2. تسبيح
   - عرض عدد التسبيحات لكل كلمة لكل مستخدم.

3. سبحان الله / الحمد لله / الله أكبر
   - زيادة عدد التسبيحات لكل كلمة.

4. الإشعارات:
   - إيقاف: يوقف الإشعارات التلقائية.
   - تشغيل: يعيد تفعيل الإشعارات التلقائية.
""")); return

    if text.lower()=="ذكرني": send_all(); return
    if text.lower()=="تسبيح":
        c = tasbih[uid]; line_bot_api.reply_message(event.reply_token,TextSendMessage(f"سبحان الله: {c['سبحان الله']}/33\nالحمد لله: {c['الحمد لله']}/33\nالله أكبر: {c['الله أكبر']}/33")); return
    if text in ("سبحان الله","الحمد لله","الله أكبر"): tasbih[uid][text]+=1; save(); c=tasbih[uid]; line_bot_api.reply_message(event.reply_token,TextSendMessage(f"سبحان الله: {c['سبحان الله']}/33\nالحمد لله: {c['الحمد لله']}/33\nالله أكبر: {c['الله أكبر']}/33")); return
    if text.lower()=="إيقاف": notifications_off.add(tid); save(); line_bot_api.reply_message(event.reply_token,TextSendMessage("تم إيقاف الإشعارات التلقائية")); return
    if text.lower()=="تشغيل": notifications_off.discard(tid); save(); line_bot_api.reply_message(event.reply_token,TextSendMessage("تم إعادة تفعيل الإشعارات التلقائية")); return

# تشغيل
if __name__=="__main__": app.run(host="0.0.0.0",port=PORT,threaded=True)
