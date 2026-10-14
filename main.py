import os
import uuid
import subprocess
import threading
import telebot
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow - Video Processing Cloud API")

# إنشاء مجلدات العمل المؤقتة
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def get_file_size_mb(file_path):
    if not os.path.exists(file_path):
        return 0.0
    return round(os.path.getsize(file_path) / (1024 * 1024), 2)

def compress_video_ffmpeg(input_path, output_path, crf_value="28"):
    """ دالة الضغط الفعلي باستخدام FFmpeg """
    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vcodec", "libx264",
        "-crf", str(crf_value),
        "-preset", "faster",
        output_path
    ]
    subprocess.run(command, check=True)

# ------------------------------------
# 🌐 مسارات واجهة الموقع (Web Endpoints)
# ------------------------------------

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """ تقديم صفحة الموقع الرئيسية """
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>صفحة index.html غير موجودة في السيرفر!</h2>"

@app.post("/api/compress")
async def process_web_video(video: UploadFile = File(...), quality: str = Form("28")):
    """ استقبال وضغط الفيديو المرفوع من واجهة الموقع """
    try:
        job_id = str(uuid.uuid4())
        input_filename = f"{job_id}_{video.filename}"
        output_filename = f"compressed_{job_id}.mp4"
        
        input_path = os.path.join(UPLOAD_DIR, input_filename)
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        # حفظ الفيديو المرفوع محلياً
        with open(input_path, "wb") as buffer:
            buffer.write(await video.read())

        original_size = get_file_size_mb(input_path)

        # تحويل وضع الجودة إلى قيمة CRF
        crf_map = {"balanced": "28", "max": "32", "high": "23"}
        crf = crf_map.get(quality, "28")

        # بدء الضغط بـ FFmpeg
        compress_video_ffmpeg(input_path, output_path, crf_value=crf)
        compressed_size = get_file_size_mb(output_path)

        saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1) if original_size > 0 else 0.0

        # تنظيف ملف المدخلات الأصلي لتوفير المساحة
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{file_name}")
def download_file(file_name: str):
    """ مسار تنزيل الفيديو المضغوط من الموقع """
    file_path = os.path.join(PROCESSED_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="الملف غير موجود أو تم حذفه لتوفير المساحة")

# ------------------------------------
# 🤖 معالجة بوت تيليجرام (Bot Handlers)
# ------------------------------------

def process_telegram_reply(job_id: str, file_path: str, chat_id: int):
    try:
        original_size = get_file_size_mb(file_path)
        output_path = os.path.join(PROCESSED_DIR, f"tg_{job_id}.mp4")

        compress_video_ffmpeg(file_path, output_path, crf_value="28")
        compressed_size = get_file_size_mb(output_path)
        
        saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1) if original_size > 0 else 0.0

        if bot:
            report_message = (
                f"✅ **تم ضغط الفيديو بنجاح!**\n\n"
                f"📦 الحجم قبل الضغط: `{original_size} MB`\n"
                f"📉 الحجم بعد الضغط: `{compressed_size} MB`\n"
                f"🔥 نسبة التوفير: `{saved_percentage}%`"
            )
            with open(output_path, 'rb') as video_file:
                bot.send_video(chat_id=chat_id, video=video_file, caption=report_message, parse_mode="Markdown")

        # تنظيف
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(output_path): os.remove(output_path)

    except Exception as e:
        if bot: bot.send_message(chat_id=chat_id, text=f"❌ حدث خطأ أثناء المعالجة: {str(e)}")

if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك في Media Flow Bot! أرسل مقطع فيديو وسأقوم بضغطه لك فوراً.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        bot.reply_to(message, "⏳ جاري تنزيل الفيديو وبدء الضغط الحقيقي...")
        try:
            chat_id = message.chat.id
            file_id = message.video.file_id if message.video else message.document.file_id
            
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            job_id = str(uuid.uuid4())
            input_path = os.path.join(UPLOAD_DIR, f"tg_in_{job_id}.mp4")
            
            with open(input_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            threading.Thread(target=process_telegram_reply, args=(job_id, input_path, chat_id)).start()

        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")

    def run_telegram_bot():
        bot.infinity_polling()
        
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    
