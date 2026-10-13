import os
import uuid
import telebot
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

# قراءة التوكن من إعدادات البيئة في Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow API & Telegram Bot with Compression Stats")

class ProcessRequest(BaseModel):
    user_id: str
    video_url: str
    action: str = "compress"

def get_file_size_mb(file_path):
    if not os.path.exists(file_path):
        return 0.0
    size_bytes = os.path.getsize(file_path)
    return round(size_bytes / (1024 * 1024), 2)

def background_media_processing(job_id: str, video_url: str, user_id: str, chat_id=None):
    print(f"[*] Starting background task {job_id} for user {user_id}...")
    
    # محاكاة حجم فيديو أصلي (مثلاً 45.5 ميغابايت)
    original_size = 45.5 
    
    # محاكاة عملية الضغط (سنستبدل هذه الخطوة لاحقاً بـ FFmpeg الحقيقي)
    import time
    time.sleep(3)
    
    # محاكاة الحجم بعد الضغط (مثلاً أصبح 12.3 ميغابايت)
    compressed_size = 12.3 
    saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1)
    
    print(f"[+] Task {job_id} completed! Original: {original_size}MB, Compressed: {compressed_size}MB")
    
    # إذا كان الطلب قادماً من تيليجرام، نرسل تقرير المقارنة للمستخدم
    if bot and chat_id:
        try:
            report_message = (
                f"✅ **تم ضغط الفيديو بنجاح!**\n\n"
                f"📦 الحجم قبل الضغط: `{original_size} MB`\n"
                f"📉 الحجم بعد الضغط: `{compressed_size} MB`\n"
                f"🔥 نسبة التوفير: `{saved_percentage}%`"
            )
            bot.send_message(chat_id=chat_id, text=report_message, parse_mode="Markdown")
        except Exception as e:
            print(f"[-] Failed to send Telegram notification: {e}")

@app.get("/")
def home():
    return {"status": "online", "message": "Media Flow API is running and ready for compression stats!"}

@app.post("/api/v1/process")
def process_media(request: ProcessRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(background_media_processing, job_id, request.video_url, request.user_id)
    
    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "message": "Task received. Processing and calculating size reduction."
    }

# إعداد تفاعل بوت تيليجرام لاستقبال الفيديوهات وعرض المقارنة
if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك في بوت معالجة الميديا! أرسل لي أي فيديو وسأقوم بضغطه وحساب نسبة توفير المساحة لك.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        bot.reply_to(message, "⏳ جاري استلام الفيديو، حساب الحجم، وبدء الضغط...")
        try:
            chat_id = message.chat.id
            user_id = str(chat_id)
            
            # استخراج رابط الملف من تيليجرام
            file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            job_id = str(uuid.uuid4())
            background_media_processing(job_id, file_url, user_id, chat_id=chat_id)
            
        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ أثناء استقبال الملف: {str(e)}")

    import threading
    def run_telegram_bot():
        print("[*] Telegram Bot polling started with stats support...")
        bot.infinity_polling()
        
    threading.Thread(target=run_telegram_bot, daemon=True).start()
