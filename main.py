import time
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from optimizer import optimize_image_for_ai

app = FastAPI(
    title="MediaFlow API",
    description="High-performance middleware to optimize and compress images for AI LLMs (Vision Models).",
    version="1.0.0"
)

# السماح للاتصالات من أي تطبيق أو موقع (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "MediaFlow API",
        "version": "1.0.0",
        "message": "Send POST requests to /v1/optimize to compress images for AI processing."
    }

@app.post("/v1/optimize")
async def optimize_image(
    file: UploadFile = File(...),
    max_dimension: int = Query(1024, description="Max width or height in pixels"),
    quality: int = Query(80, description="Image quality (1-100)")
):
    # التأكد من أن الملف المرفوع صورة
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    start_time = time.time()
    
    try:
        image_bytes = await file.read()
        original_size = len(image_bytes)

        # تنفيذ عملية الضغط والمعالجة
        optimized_bytes = optimize_image_for_ai(
            image_bytes=image_bytes,
            max_dimension=max_dimension,
            quality=quality
        )
        
        optimized_size = len(optimized_bytes)
        saved_bytes = original_size - optimized_size
        saved_percentage = (saved_bytes / original_size) * 100 if original_size > 0 else 0
        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        # إرجاع الصورة المضغوطة مع الترويسات التي توضح نسبة التوفير
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")
