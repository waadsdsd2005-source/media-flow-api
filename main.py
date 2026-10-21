import os
import secrets
import time
import threading
import requests
from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
import io

app = FastAPI(title="Kwaku Media API", version="7.0")

# المتغيرات الأساسية
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OXAPAY_API_KEY = os.getenv("OXAPAY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://media-flow-api.onrender.com")

# نظام منع السبات الذكي (Self-Ping 24/7)
def keep_alive():
    while True:
        time.sleep(600)  # كل 10 دقائق
        try:
            requests.get(RENDER_EXTERNAL_URL)
            print("Keep-Alive ping sent successfully.")
        except Exception as e:
            print(f"Keep-Alive ping failed: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

def send_telegram_alert(message: str):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Telegram error: {e}")

class CheckoutRequest(BaseModel):
    api_key: str
    plan: str
    email: str

class FreeTrialRequest(BaseModel):
    email: str

class CheckBalanceRequest(BaseModel):
    api_key: str

class FeedbackRequest(BaseModel):
    api_key: str
    feedback_type: str
    message: str

@app.get("/", response_class=HTMLResponse)
def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h2>منصة كواكو ميديا تعمل بنجاح!</h2>"

# ضغط الصور المباشر بدون مفتاح (تجربة حتى 10 صور)
@app.post("/v1/compress-direct")
async def compress_direct(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # تحويل الألوان وتحسين الجودة للضغط
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        compressed_filename = f"compressed_{secrets.token_hex(4)}.jpg"
        file_path = os.path.join(output_dir, compressed_filename)
        
        image.save(file_path, "JPEG", optimize=True, quality=60)
        
        send_telegram_alert(f"⚡ **تجربة ضغط مباشرة على كواكو ميديا!**\n- الملف: `{file.filename}`")
        return {"status": "success", "download_url": f"/v1/download/{compressed_filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل ضغط الصورة: {str(e)}")

@app.get("/v1/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join("downloads", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="الملف غير موجود.")

@app.post("/v1/free-trial")
def activate_free_trial(data: FreeTrialRequest):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    clean_url = SUPABASE_URL.strip().rstrip('/')
    
    try:
        new_key = f"mf_live_{secrets.token_hex(8)}"
        payload = {"id": new_key, "email": data.email, "tokens": 500, "has_used_trial": True}
        
        res = requests.post(f"{clean_url}/rest/v1/profiles", headers=headers, json=payload)
        if res.status_code in [200, 201]:
            send_telegram_alert(f"🚀 **مفتاح كواكو ميديا جديد!**\n- المفتاح: `{new_key}`\n- البريد: `{data.email}`")
            return {"status": "success", "api_key": new_key, "tokens": 500}
        else:
            raise HTTPException(status_code=500, detail=f"خطأ في قاعدة البيانات: {res.text}")
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/check-balance")
def check_balance(data: CheckBalanceRequest):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    clean_url = SUPABASE_URL.strip().rstrip('/')
    res = requests.get(f"{clean_url}/rest/v1/profiles?id=eq.{data.api_key}", headers=headers)
    
    if res.status_code == 200 and res.json():
        user = res.json()[0]
        return {"tokens": user.get("tokens", 0), "email": user.get("email", "غير متوفر")}
    raise HTTPException(status_code=404, detail="المفتاح غير موجود في قاعدة البيانات.")

@app.post("/v1/payments/create-invoice")
def create_oxapay_invoice(data: CheckoutRequest):
    payload = {
        "merchant": OXAPAY_API_KEY,
        "amount": 10,
        "currency": "USD",
        "lifeTime": 60,
        "orderId": f"sub_{data.api_key}_{data.plan}",
        "email": data.email,
        "callbackUrl": f"{RENDER_EXTERNAL_URL}/v1/payments/webhook"
    }
    res = requests.post("https://api.oxapay.com/merchants/request", json=payload).json()
    if res.get("result") == 100:
        return {"status": "success", "payment_url": res.get("payLink")}
    raise HTTPException(status_code=400, detail="فشل الاتصال ببوابة الدفع OxaPay.")

@app.post("/v1/payments/webhook")
async def oxapay_webhook(request: Request):
    try:
        body = await request.json()
        if body.get("status") in ["Complete", 1]:
            parts = body.get("orderId").split("_")
            api_key, plan = parts[1], parts[2]
            add_tokens = 10000 if plan == "pro" else 70000
            
            clean_url = SUPABASE_URL.strip().rstrip('/')
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            
            get_res = requests.get(f"{clean_url}/rest/v1/profiles?id=eq.{api_key}", headers=headers).json()
            if get_res:
                curr = get_res[0].get("tokens", 0)
                requests.patch(f"{clean_url}/rest/v1/profiles?id=eq.{api_key}", headers=headers, json={"tokens": curr + add_tokens})
                send_telegram_alert(f"💰 **اشتراك جديد شُحن تلقائياً في كواكو ميديا!**\n- المفتاح: `{api_key}`\n- الرصيد الجديد: {curr + add_tokens}")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/v1/feedback")
def receive_feedback(data: FeedbackRequest):
    send_telegram_alert(f"📩 **رسالة/شكوى جديدة من كواكو ميديا:**\n- المفتاح: `{data.api_key}`\n- الرسالة: {data.message}")
    return {"status": "success"}
