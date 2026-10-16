import time
import asyncio
import httpx
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from optimizer import optimize_image_for_ai
import zipfile
import io

app = FastAPI(
    title="MediaFlow API",
    description="High-performance, fault-tolerant middleware to optimize multiple images for AI LLMs.",
    version="1.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛡️ نظام منع السبات الذاتي (Anti-Sleep Mechanism)
@app.on_event("startup")
async def startup_event():
    async def keep_alive():
        while True:
            await asyncio.sleep(600)  # كل 10 دقائق
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

# 1. مسار معالجة صورة فردية
@app.post("/v1/optimize")
async def optimize_image(
    file: UploadFile = File(...),
    max_dimension: int = Query(1024, description="Max width or height in pixels"),
    quality: int = Query(80, description="Image quality (1-100)")
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid image.")

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

# 2. مسار معالجة صور متعددة دفعة واحدة (Batch Processing)
@app.post("/v1/optimize-batch")
async def optimize_multiple_images(
    files: List[UploadFile] = File(...),
    max_dimension: int = Query(1024),
    quality: int = Query(80)
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images allowed per batch to protect server memory.")
    
    if len(files) == 1:
        # إذا تم اختيار صورة واحدة، نمررها للطريقة العادية
        return await optimize_image(files[0], max_dimension, quality)
    
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
        raise HTTPException(status_code=500, detail=f"Batch processing failed safely: {str(e)}")
                
