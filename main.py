import time
import asyncio
import httpx
import uuid
import io
import zipfile
import os
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Header
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from optimizer import optimize_image_for_ai
from supabase import create_client, Client
import telebot

# 🔑 قراءة الإعدادات آمنياً من متغيرات البيئة (Render Environment Variables)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://iicfzhonuanuugaxtwgs.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# إنشاء اتصال قاعدة البيانات فقط إذا تم توفير المفتاح
supabase: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_KEY else None
bot: Optional[telebot.TeleBot] = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False) if TELEGRAM_BOT_TOKEN else None

app = FastAPI(
    title="MediaFlow API",
    description="High-performance AI Image Optimizer middleware backed by Supabase & Telegram Control.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛡️ نظام منع السبات الذاتي (Anti-Sleep)
@app.on_event("startup")
async def startup_event():
    async def keep_alive():
        while True:
            await asyncio.sleep(600)
            try:
                async with httpx.AsyncClient() as client:
                    await client.get("https://media-flow-api.onrender.com/", timeout=5.0)
            except Exception:
                pass
    asyncio.create_task(keep_alive())

# الواجهة الرئيسية (Landing Page)
@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>MediaFlow API is Running Online 🚀</h1>"

# 🔑 1. توليد مفتاح API مجاني جديد وحفظه في Supabase
@app.post("/v1/generate-key")
def generate_free_key():
    new_key = f"mf_live_{uuid.uuid4().hex[:16]}"
    if not supabase:
        return {"api_key": new_key, "plan": "free", "credits_remaining": 1000, "status": "active_local"}
    
    try:
        data = {
            "key_value": new_key,
            "plan_type": "free",
            "credits_remaining": 1000
        }
        supabase.table("api_keys").insert(data).execute()
        return {
            "api_key": new_key,
            "plan": "free",
            "credits_remaining": 1000,
            "status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate key: {str(e)}")

# 🛠️ دالة التحقق من صحة المفتاح وخصم الرصيد من Supabase
def verify_and_deduct_key(x_api_key: Optional[str], cost: int = 1):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key missing. Pass 'x-api-key' in request headers.")

    if not supabase:
        return {"key_value": x_api_key, "credits_remaining": 1000}

    response = supabase.table("api_keys").select("*").eq("key_value", x_api_key).execute()
    records = response.data

    if not records or len(records) == 0:
        raise HTTPException(status_code=401, detail="Invalid API Key.")

    key_info = records[0]
    remaining = key_info.get("credits_remaining", 0)

    if remaining < cost:
        raise HTTPException(status_code=402, detail="Quota exceeded. Please upgrade your plan via USDT.")

    # خصم الرصيد وتحديث القاعدة
    new_balance = remaining - cost
    supabase.table("api_keys").update({"credits_remaining": new_balance}).eq("key_value", x_api_key).execute()
    
    return key_info

# 2. معالجة صورة فردية
@app.post("/v1/optimize")
async def optimize_image(
    file: UploadFile = File(...),
    max_dimension: int = Query(1024),
    quality: int = Query(80),
    x_api_key: Optional[str] = Header(None)
):
    verify_and_deduct_key(x_api_key, cost=1)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Upload an image.")

    start_time = time.time()
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Image is empty.")
        if len(image_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size exceeds 25MB Limit.")

        original_size = len(image_bytes)
        optimized_bytes = optimize_image_for_ai(image_bytes=image_bytes, max_dimension=max_dimension, quality=quality)
        optimized_size = len(optimized_bytes)
        
        saved_bytes = original_size - optimized_size
        saved_percentage = (saved_bytes / original_size) * 100 if original_size > 0 else 0
        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        headers = {
            "X-Original-Size-Bytes": str(original_size),
            "X-Optimized-Size-Bytes": str(optimized_size),
            "X-Saved-Percentage": f"{saved_percentage:.2f}%",
            "X-Execution-Time-MS": f"{execution_time_ms}ms"
        }

        return Response(content=optimized_bytes, media_type="image/webp", headers=headers)

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# 3. معالجة الصور الجماعية (Batch Processing)
@app.post("/v1/optimize-batch")
async def optimize_multiple_images(
    files: List[UploadFile] = File(...),
    max_dimension: int = Query(1024),
    quality: int = Query(80),
    x_api_key: Optional[str] = Header(None)
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images allowed per batch.")

    verify_and_deduct_key(x_api_key, cost=len(files))
    
    if len(files) == 1:
        return await optimize_image(files[0], max_dimension, quality, x_api_key)
    
    try:
        zip_buffer = io.BytesIO()
        total_orig = 0
        total_opt = 0

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for idx, file in enumerate(files):
                if not file.content_type or not file.content_type.startswith("image/"):
                    continue
                image_bytes = await file.read()
                if len(image_bytes) == 0:
                    continue
                
                total_orig += len(image_bytes)
                optimized_bytes = optimize_image_for_ai(image_bytes, max_dimension, quality)
                total_opt += len(optimized_bytes)
                
                zip_file.writestr(f"optimized_{idx+1}.webp", optimized_bytes)
                
        zip_buffer.seek(0)
        saved_total_pct = ((total_orig - total_opt) / total_orig) * 100 if total_orig > 0 else 0

        headers = {
            "Content-Disposition": "attachment; filename=mediaflow_batch.zip",
            "X-Total-Original-Size": str(total_orig),
            "X-Total-Optimized-Size": str(total_opt),
            "X-Total-Saved-Percentage": f"{saved_total_pct:.2f}%"
        }

        return Response(content=zip_buffer.getvalue(), media_type="application/zip", headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

# 🤖 بوت تليجرام المدمج للتحكم الإداري
if bot:
    @bot.message_handler(commands=['start', 'stats'])
    def bot_stats(message):
        if ADMIN_CHAT_ID and message.chat.id != ADMIN_CHAT_ID:
            return
        try:
            if supabase:
                res = supabase.table("api_keys").select("*").execute()
                total = len(res.data)
                bot.reply_to(message, f"📊 MediaFlow Status:\nActive API Keys in Supabase: {total} ✅")
            else:
                bot.reply_to(message, "Supabase connection is not configured.")
        except Exception as e:
            bot.reply_to(message, f"Error: {str(e)}")

    @bot.message_handler(commands=['upgrade'])
    def bot_upgrade(message):
        if ADMIN_CHAT_ID and message.chat.id != ADMIN_CHAT_ID:
            return
        try:
            args = message.text.split()
            target_key = args[1]
            credits = int(args[2])
            if supabase:
                supabase.table("api_keys").update({"credits_remaining": credits, "plan_type": "pro"}).eq("key_value", target_key).execute()
                bot.reply_to(message, f"✅ Key {target_key} upgraded successfully to {credits} credits!")
            else:
                bot.reply_to(message, "Supabase is not configured.")
        except Exception as e:
            bot.reply_to(message, f"Usage: /upgrade KEY CREDITS\nError: {str(e)}")

    def run_telegram_bot():
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception:
            pass

    import threading
    threading.Thread(target=run_telegram_bot, daemon=True).start()
