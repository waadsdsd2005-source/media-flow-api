import os
import uuid
import subprocess
import threading
import telebot
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow - Background Video Processing API")

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

jobs_status = {}

def get_file_size_mb(file_path):
    if not os.path.exists(file_path):
        return 0.0
    return round(os.path.getsize(file_path) / (1024 * 1024), 2)

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>صفحة index.html غير موجودة!</h2>"

@app.post("/api/compress")
async def process_web_video(background_tasks: BackgroundTasks, video: UploadFile = File(...), quality: str = Form("28")):
    try:
        job_id = str(uuid.uuid4())
        input_filename = f"{job_id}_{video.filename}"
        output_filename = f"compressed_{job_id}.mp4"
        
        input_path = os.path.join(UPLOAD_DIR, input_filename)
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        with open(input_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)

        return {
            "status": "queued",
            "job_id": job_id,
            "message": "تم استلام الفيديو بنجاح"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{file_name}")
def download_file(file_name: str):
    file_path = os.path.join(PROCESSED_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="الملف غير موجود أو انتهت صلاحيته")

# إعدادات بوت تيليجرام مع إرسال سبب الفشل بدقة
if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك في Media Flow Bot! أرسل أي فيديو وسأعالج ضغطه لك في الخلفية مع إرسال التقرير أو سبب الخطأ إن حدث.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        sent_msg = bot.reply_to(message, "⏳ تم استلام الفيديو، جاري العمل على ضغطه في الخلفية...")
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
            
            def process_tg():
                try:
                    original_size = get_file_size_mb(input_path)
                    
                    # محاولة تشغيل FFmpeg وضبطه ليتعامل مع الفيديوهات
                    command = [
                        "ffmpeg", "-y",
                        "-i", input_path,
                        "-vcodec", "libx264",
                        "-crf", "28",
                        "-preset", "ultrafast",
                        output_path
                    ]
                    
                    result = subprocess.run(command, capture_output=True, text=True)
                    
                    # إذا حدث خطأ في تشغيل FFmpeg
                    if result.returncode != 0:
                        error_detail = result.stderr[-500:] if result.stderr else "خطأ غير معروف في محرك FFmpeg"
                        raise Exception(f"فشل محرك المعالجة:\n`{error_detail}`")

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

                except Exception as ex:
                    # إرسال سبب الفشل المفصل مباشرة إلى المستخدم عبر البوت
                    error_msg = f"❌ **فشلت عملية ضغط الفيديو!**\n\n**السبب التقني:**\n`{str(ex)}`"
                    bot.send_message(chat_id=chat_id, text=error_msg, parse_mode="Markdown")

                finally:
                    # تنظيف الملفات المؤقتة في كلتا الحالتين (النجاح أو الفشل)
                    if os.path.exists(input_path): os.remove(input_path)
                    if os.path.exists(output_path): os.remove(output_path)
                    try:
                        bot.delete_message(chat_id, sent_msg.message_id)
                    except:
                        pass

            threading.Thread(target=process_tg, daemon=True).start()

        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ أثناء استقبال الملف: {str(e)}")

    def run_telegram_bot():
        bot.infinity_polling(none_stop=True)
        
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    
