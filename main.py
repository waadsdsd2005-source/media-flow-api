import os
import uuid
import subprocess
import threading
import telebot
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow - Turbo Background Processing")

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# حد الحجم المسموح للخطة المجانية لحماية السيرفر من النفاد (25 ميغابايت)
MAX_FREE_SIZE_MB = 25.0

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

# دالة ضغط التيربو التي تعمل في الخلفية المطلقة حتى لو أغلق المستخدم الموقع
def turbo_background_compression(input_path, output_path, job_id):
    try:
        # محرك التيربو: ضغط فائق السرعة مع خفض الدقة إلى 720p لتجنب بطء المعالج المجاني
        command = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", "scale=-2:720",  # خفض الدقة لتسريع الضغط بنسبة كبيرة جداً
            "-vcodec", "libx264",
            "-crf", "28",
            "-preset", "ultrafast",
            output_path
        ]
        
        process = subprocess.run(command, capture_output=True, text=True)
        
        if process.returncode != 0:
            print(f"Turbo FFmpeg Error in Job {job_id}: {process.stderr}")

    except Exception as e:
        print(f"Exception in Turbo Job {job_id}: {str(e)}")
        
    finally:
        # تنظيف ملف الإدخال الأصلي بعد انتهاء العمل في الخلفية
        if os.path.exists(input_path):
            os.remove(input_path)

@app.post("/api/compress")
async def process_web_video(background_tasks: BackgroundTasks, video: UploadFile = File(...), quality: str = Form("28")):
    input_path = None
    output_path = None
    try:
        job_id = str(uuid.uuid4())
        input_filename = f"{job_id}_{video.filename}"
        output_filename = f"compressed_{job_id}.mp4"
        
        input_path = os.path.join(UPLOAD_DIR, input_filename)
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        # حفظ الملف المرفوع مؤقتاً
        with open(input_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)

        original_size = get_file_size_mb(input_path)

        # حراسة السيرفر من الملفات الكبيرة جداً
        if original_size > MAX_FREE_SIZE_MB:
            if os.path.exists(input_path):
                os.remove(input_path)
            raise HTTPException(
                status_code=400, 
                detail=f"حجم الملف ({original_size} MB) يتجاوز الحد المجاني ({MAX_FREE_SIZE_MB} MB). يرجى استخدام ملف أصغر."
            )

        # إطلاق عملية التيربو في الخلفية المستقلة تماماً عن المتصفح
        background_tasks.add_task(turbo_background_compression, input_path, output_path, job_id)

        # استجابة فورية للموقع بأن العمل بدأ في الخلفية ويمكن للمستخدم إغلاق الصفحة بأمان
        return {
            "status": "success",
            "job_id": job_id,
            "download_url": f"/api/download/{output_filename}",
            "message": "تم بدء ضغط التيربو في الخلفية! يمكنك إغلاق الموقع وسيبقى السيرفر يعمل حتى يكتمل."
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{file_name}")
def download_file(file_name: str):
    file_path = os.path.join(PROCESSED_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="الملف غير موجود أو لم يكتمل الضغط في الخلفية بعد")

# إعدادات بوت تيليجرام بنظام التيربو والخلفية المستقلة
if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك في بوت Media Flow (تيربو)! أرسل الفيديو (أقل من 25 ميغا) وسأقوم بضغطه في الخلفية وإرساله لك.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        try:
            chat_id = message.chat.id
            file_id = message.video.file_id if message.video else message.document.file_id
            
            file_info = bot.get_file(file_id)
            file_size_bytes = file_info.file_size if hasattr(file_info, 'file_size') else 0
            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

            if file_size_mb > MAX_FREE_SIZE_MB:
                bot.reply_to(message, f"❌ عذراً، حجم الفيديو ({file_size_mb} MB) يتجاوز الحد المسموح بالخطة المجانية ({MAX_FREE_SIZE_MB} MB).")
                return

            sent_msg = bot.reply_to(message, "🚀 جارٍ ضغط الفيديو بتكنولوجيا التيربو في الخلفية...")
            
            downloaded_file = bot.download_file(file_info.file_path)
            job_id = str(uuid.uuid4())
            input_path = os.path.join(UPLOAD_DIR, f"tg_in_{job_id}.mp4")
            output_path = os.path.join(PROCESSED_DIR, f"tg_out_{job_id}.mp4")
            
            with open(input_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            def process_tg_turbo():
                try:
                    original_size = get_file_size_mb(input_path)
                    
                    command = [
                        "ffmpeg", "-y",
                        "-i", input_path,
                        "-vf", "scale=-2:720",
                        "-vcodec", "libx264",
                        "-crf", "28",
                        "-preset", "ultrafast",
                        output_path
                    ]
                    
                    process = subprocess.run(command, capture_output=True, text=True)
                    
                    if process.returncode != 0:
                        raise Exception("فشل محرك التيربو في معالجة الفيديو")

                    compressed_size = get_file_size_mb(output_path)
                    saved_percentage = round(((original_size - compressed_size) / original_size) * 100, 1) if original_size > 0 else 0.0

                    report_message = (
                        f"🚀 **تم ضغط الفيديو (تيربو) بنجاح!**\n\n"
                        f"📦 الحجم قبل: `{original_size} MB`\n"
                        f"📉 الحجم بعد: `{compressed_size} MB`\n"
                        f"🔥 التوفير: `{saved_percentage}%`"
                    )
                    
                    with open(output_path, 'rb') as video_file:
                        bot.send_video(chat_id=chat_id, video=video_file, caption=report_message, parse_mode="Markdown")

                except Exception as ex:
                    bot.send_message(chat_id=chat_id, text=f"❌ حدث خطأ:\n`{str(ex)}`", parse_mode="Markdown")

                finally:
                    if os.path.exists(input_path): os.remove(input_path)
                    if os.path.exists(output_path): os.remove(output_path)
                    try:
                        bot.delete_message(chat_id, sent_msg.message_id)
                    except:
                        pass

            threading.Thread(target=process_tg_turbo, daemon=True).start()

        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ في استقبال الملف: {str(e)}")

    def run_telegram_bot():
        bot.infinity_polling(none_stop=True)
        
    threading.Thread(target=run_telegram_bot, daemon=True).start()
                        
