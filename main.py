import os
import uuid
import subprocess
import threading
import telebot
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow - Video Processing Cloud API")

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def get_file_size_mb(file_path):
    if not os.path.exists(file_path):
        return 0.0
    return round(os.path.getsize(file_path) / (1024 * 1024), 2)

def compress_video_ffmpeg(input_path, output_path, crf_value="28"):
    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vcodec", "libx264",
        "-crf", str(crf_value),
        "-preset", "ultrafast",
        output_path
    ]
    subprocess.run(command, check=True)

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>صفحة index.html غير موجودة!</h2>"

@app.post("/api/compress")
async def process_web_video(video: UploadFile = File(...), quality: str = Form("28")):
    try:
        job_id = str(uuid.uuid4())
        input_filename = f"{job_id}_{video.filename}"
        output_filename = f"compressed_{job_id}.mp4"
        
        input_path = os.path.join(UPLOAD_DIR, input_filename)
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        with open(input_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)

        original_size = get_file_size_mb(input_path)

        # ضغط الفيديو
        compress_video_ffmpeg(input_path, output_path, crf_value=quality)
        compressed_size = get_file_size_mb(output_path)

        saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1) if original_size > 0 else 0.0

        if os.path.exists(input_path):
            os.remove(input_path)

        return {
            "status": "success",
            "job_id": job_id,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "saved_percentage": saved_percentage,
            "download_url": f"/api/download/{output_filename}"
        }

    except Exception as e:
        if os.path.exists(input_path): os.remove(input_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{file_name}")
def download_file(file_name: str):
    file_path = os.path.join(PROCESSED_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="الملف غير موجود أو انتهت صلاحيته")

# إعدادات بوت تيليجرام
if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك في Media Flow Bot! أرسل مقطع فيديو وسأقوم بضغطه لك فوراً.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        sent_msg = bot.reply_to(message, "⏳ جاري تنزيل الفيديو ومعالجته عبر السيرفر...")
        try:
            chat_id = message.chat.id
            file_id = message.video.file_id if message.video else message.document.file_id
            
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            job_id = str(uuid.uuid4())
            input_path = os.path.join(UPLOAD_DIR, f"tg_in_{job_id}.mp4")
            output_path = os.path.join(PROCESSED_DIR, f"tg_out_{job_id}.mp4")
            
            with open(input_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            original_size = get_file_size_mb(input_path)
            compress_video_ffmpeg(input_path, output_path, crf_value="28")
            compressed_size = get_file_size_mb(output_path)
            
            saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1) if original_size > 0 else 0.0

            report_message = (
                f"✅ **تم ضغط الفيديو بنجاح!**\n\n"
                f"📦 الحجم قبل: `{original_size} MB`\n"
                f"📉 الحجم بعد: `{compressed_size} MB`\n"
                f"🔥 التوفير: `{saved_percentage}%`"
            )
            
            with open(output_path, 'rb') as video_file:
                bot.send_video(chat_id=chat_id, video=video_file, caption=report_message, parse_mode="Markdown")

            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)
            bot.delete_message(chat_id, sent_msg.message_id)

        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ أثناء المعالجة: {str(e)}")

    def run_telegram_bot():
        print("Telegram bot started polling...")
        bot.infinity_polling(none_stop=True)
        
    # تشغيل البوت بخيط مستقل
    t = threading.Thread(target=run_telegram_bot, daemon=True)
    t.start()
