import time
import asyncio
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from optimizer import optimize_image_for_ai

app = FastAPI(
    title="MediaFlow API",
    description="High-performance, fault-tolerant middleware to optimize images for AI LLMs.",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛡️ نظام منع السبات الذاتي (Self-Ping / Anti-Sleep Mechanism)
# يقوم السيرفر بإرسال طلب خفي لنفسه كل 10 دقائق ليظل نشطاً طوال الوقت.
@app.on_event("startup")
async def startup_event():
    async def keep_alive():
        while True:
            await asyncio.sleep(600)  # كل 10 دقائق
            try:
                # ضع رابط سيرفرك الفعلي هنا على Render ليقوم بإنعاش نفسه
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

@app.post("/v1/optimize")
async def optimize_image(
    file: UploadFile = File(...),
    max_dimension: int = Query(1024, description="Max width or height in pixels"),
    quality: int = Query(80, description="Image quality (1-100)")
):
    # التحقق من نوع الملف لمنع الانهيار عند رفع ملفات غير مدعومة
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Please upload a valid image (JPEG, PNG, WebP, etc.)."
        )

    start_time = time.time()
    
    try:
        image_bytes = await file.read()
        
        # حماية ضد الملفات الفارغة أو الضخمة جداً التي قد تسبب Out of Memory
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")
        if len(image_bytes) > 25 * 1024 * 1024:  # أكثر من 25 ميجابايت
            raise HTTPException(status_code=400, detail="Image file is too large (Max 25MB).")

        original_size = len(image_bytes)

        # تنفيذ الضغط في بيئة آمنة
        optimized_bytes = optimize_image_for_ai(
            image_bytes=image_bytes,
            max_dimension=max_dimension,
            quality=quality
        )
        
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

        return Response(
            content=optimized_bytes,
            media_type="image/webp",
            headers=headers
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        # أسوأ الاحتمالات: إذا حدث خطأ غير متوقع في معالجة الصورة، لا ينفجر السيرفر بل يرسل رسالة خطأ واضحة
        raise HTTPException(
            status_code=500, 
            detail=f"Image processing failed safely: The image might be corrupted or in an unsupported format."
        )
