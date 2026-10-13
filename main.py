import os
import uuid
import subprocess
import telebot
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow Real Video Processing API")

class ProcessRequest(BaseModel):
    user_id: str
    video_url: str
    action: str = "compress"

def get_file_size_mb(file_path):
    if not os.path.exists(file_path):
        return 0.0
    return round(os.path.getsize(file_path) / (1024 * 1024), 2)

def compress_video_ffmpeg(input_path, output_path):
    """ ضغط الفيديو بنسبة تتراوح بين 50% إلى 70% مع الحفاظ على الجودة """
    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vcodec", "libx264",
        "-crf", "28",             # درجة الضغط (كلما زاد الرقم قل الحجم)
        "-preset", "faster",
        output_path
    ]
    subprocess.run(command, check=True)

def process_and_reply(job_id: str, file_path: str, user_id: str, chat_id=None):
    try:
        original_size = get_file_size_mb(file_path)
        output_path = f"compressed_{job_id}.mp4"

        # الضغط الفعلي
        compress_video_ffmpeg(file_path, output_path)
        compressed_size = get_file_size_mb(output_path)
        
        saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1) if original_size > 0 else 0.0

        if bot and chat_id:
            report_message = (
                f"✅ **تم ضغط الفيديو بنجاح!**\n\n"
                f"📦 الحجم قبل الضغط: `{original_size} MB`\n"
                f"📉 الحجم بعد الضغط: `{compressed_size} MB`\n"
                f"🔥 نسبة التوفير: `{saved_percentage}%`"
            )
            # إرسال الفيديو المضغوط الحقيقي للمستخدم
            with open(output_path, 'rb') as video_file:
                bot.send_video(chat_id=chat_id, video=video_file, caption=report_message, parse_mode="Markdown")

        # تنظيف الملفات المؤقتة لتوفير مساحة السيرفر
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(output_path): os.remove(output_path)

    except Exception as e:
        print(f"[-] Processing Error: {e}")
        if bot and chat_id:
            bot.send_message(chat_id=chat_id, text=f"❌ حدث خطأ أثناء المعالجة: {str(e)}")

@app.get("/")
def home():
    return {"status": "online", "message": "Real FFmpeg Compression Engine is Live!"}

if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك! أرسل لي أي فيديو (أقل من 20 ميغابايت) وسأقوم بضغطه حقيقياً وإرساله لك.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        bot.reply_to(message, "⏳ جاري تنزيل الفيديو وبدء الضغط الحقيقي...")
        try:
            chat_id = message.chat.id
            file_id = message.video.file_id if message.video else message.document.file_id
            
            # تنزيل الفيديو إلى السيرفر
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            job_id = str(uuid.uuid4())
            input_path = f"input_{job_id}.mp4"
            
            with open(input_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            import threading
            threading.Thread(target=process_and_reply, args=(job_id, input_path, str(chat_id), chat_id)).start()

        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")

    import threading
    def run_telegram_bot():
        bot.infinity_polling()
        
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    
