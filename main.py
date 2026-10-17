import time
import asyncio
import httpx
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Header
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from optimizer import optimize_image_for_ai
import zipfile
import io
import uuid

app = FastAPI(
    title="MediaFlow API",
    description="High-performance middleware with API Key protection.",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# قاعدة بيانات مؤقتة لمفاتيح الـ API التجريبية (Demo Keys)
VALID_API_KEYS = {"mediaflow_demo_12345"}

# 🛡️ نظام منع السبات الذاتي
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

@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>MediaFlow API is Running Online 🚀</h1>"

# 🔑 مسار لتوليد مفتاح API مجاني للمطورين
@app.post("/v1/generate-key")
def generate_free_key():
    new_key = f"mf_live_{uuid.uuid4().hex[:16]}"
    VALID_API_KEYS.add(new_key)
    return {"api_key": new_key, "limit": "1000 requests/month", "status": "active"}

# 1. مسار معالجة صورة فردية (مع التحقق من المفتاح)
@app.post("/v1/optimize")
async def optimize_image(
    file: UploadFile = File(...),
    max_dimension: int = Query(1024),
    quality: int = Query(80),
    x_api_key: Optional[str] = Header(None)
):
    # إذا كان الطلب من المتصفح المباشر أو بمفتاح صحيح نمرره
    if x_api_key and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key. Get a free key at home page.")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    start_time = time.time()
    
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")
        if len(image_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image file is too large (Max 25MB).")

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
        raise HTTPException(status_code=500, detail=f"Image processing failed safely: {str(e)}")

# 2. مسار معالجة صور متعددة
@app.post("/v1/optimize-batch")
async def optimize_multiple_images(
    files: List[UploadFile] = File(...),
    max_dimension: int = Query(1024),
    quality: int = Query(80),
    x_api_key: Optional[str] = Header(None)
):
    if x_api_key and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key.")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images allowed per batch.")
    
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
