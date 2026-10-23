import os
import secrets
import time
import threading
import requests
from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from PIL import Image
import io

app = FastAPI(title="Kwaku Media API", version="9.0")

# System Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OXAPAY_API_KEY = os.getenv("OXAPAY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://media-flow-api.onrender.com")

# Self-Ping Keep Alive Engine (24/7 Service)
def keep_alive():
    while True:
        time.sleep(600)
        try:
            requests.get(RENDER_EXTERNAL_URL)
        except Exception:
            pass

threading.Thread(target=keep_alive, daemon=True).start()

# Telegram Alert System with Admin Action Keyboards
def send_telegram_alert(message: str, reply_markup=None):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Telegram alert error: {e}")

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
        return "<h2>Kwaku Media API is running successfully!</h2>"

# Direct Free Compression (Web Interface Preview)
@app.post("/v1/compress-direct")
async def compress_direct(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        original_size_kb = len(contents) / 1024
        
        image = Image.open(io.BytesIO(contents))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        os.makedirs("downloads", exist_ok=True)
        filename = f"compressed_{secrets.token_hex(4)}.jpg"
        file_path = os.path.join("downloads", filename)
        
        image.save(file_path, "JPEG", optimize=True, quality=60)
        compressed_size_kb = os.path.getsize(file_path) / 1024
        
        saved_percent = round(((original_size_kb - compressed_size_kb) / original_size_kb) * 100, 1) if original_size_kb > 0 else 0
        
        send_telegram_alert(f"⚡ **Direct Web Compression:**\n- Original Size: {round(original_size_kb, 1)} KB\n- Compressed Size: {round(compressed_size_kb, 1)} KB\n- Savings: {saved_percent}%")
        return {
            "status": "success",
            "original_size": round(original_size_kb, 1),
            "compressed_size": round(compressed_size_kb, 1),
            "saved_percent": saved_percent,
            "download_url": f"/v1/download/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing Error: {str(e)}")

# API Key Authenticated Compression with Token Deduction
@app.post("/v1/compress-with-key")
async def compress_with_key(api_key: str = Form(...), file: UploadFile = File(...)):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    clean_url = SUPABASE_URL.strip().rstrip('/')
    
    # 1. Verify API Key and check remaining balance in Supabase
    res = requests.get(f"{clean_url}/rest/v1/profiles?id=eq.{api_key}", headers=headers)
    if res.status_code != 200 or not res.json():
        raise HTTPException(status_code=401, detail="Invalid API Key.")
        
    user = res.json()[0]
    current_tokens = user.get("tokens", 0)
    
    if current_tokens <= 0:
        raise HTTPException(status_code=403, detail="Insufficient balance. Please upgrade your subscription plan.")
        
    try:
        contents = await file.read()
        original_size_kb = len(contents) / 1024
        
        image = Image.open(io.BytesIO(contents))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        os.makedirs("downloads", exist_ok=True)
        filename = f"compressed_{secrets.token_hex(4)}.jpg"
        file_path = os.path.join("downloads", filename)
        
        image.save(file_path, "JPEG", optimize=True, quality=60)
        compressed_size_kb = os.path.getsize(file_path) / 1024
        saved_percent = round(((original_size_kb - compressed_size_kb) / original_size_kb) * 100, 1) if original_size_kb > 0 else 0
        
        # 2. Deduct 1 Token from Supabase Database
        new_balance = current_tokens - 1
        patch_headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        requests.patch(f"{clean_url}/rest/v1/profiles?id=eq.{api_key}", headers=patch_headers, json={"tokens": new_balance})
        
        admin_keyboard = {
            "inline_keyboard": [
                [{"text": "🔍 Check Key Balance", "callback_data": f"check_{api_key}"}],
                [{"text": "❌ Ban User", "callback_data": f"ban_{api_key}"}]
            ]
        }
        send_telegram_alert(f"📉 **API Compression Executed & Token Deducted:**\n- API Key: `{api_key}`\n- Remaining Tokens: `{new_balance}`\n- Saved: {saved_percent}%", admin_keyboard)
        
        return {
            "status": "success",
            "api_key": api_key,
            "remaining_tokens": new_balance,
            "original_size_kb": round(original_size_kb, 1),
            "compressed_size_kb": round(compressed_size_kb, 1),
            "saved_percent": saved_percent,
            "download_url": f"/v1/download/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing Error: {str(e)}")

@app.get("/v1/download/{filename}")
def download_file(filename: str):
    path = os.path.join("downloads", filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="File not found")

# Activate or Retrieve Free Trial Key (Duplicate Email Protection)
@app.post("/v1/free-trial")
def activate_free_trial(data: FreeTrialRequest):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    clean_url = SUPABASE_URL.strip().rstrip('/')
    
    try:
        # Check if email is already registered
        check_res = requests.get(f"{clean_url}/rest/v1/profiles?email=eq.{data.email}", headers=headers)
        
        if check_res.status_code == 200 and check_res.json():
            existing_user = check_res.json()[0]
            existing_key = existing_user.get("id")
            tokens = existing_user.get("tokens", 0)
            
            admin_keyboard = {
                "inline_keyboard": [
                    [{"text": "🔍 Inspect Key", "callback_data": f"check_{existing_key}"}],
                    [{"text": "❌ Ban User", "callback_data": f"ban_{existing_key}"}]
                ]
            }
            send_telegram_alert(f"🔑 **Existing Key Requested:**\n- Email: `{data.email}`\n- Key: `{existing_key}`\n- Balance: `{tokens}` Tokens", admin_keyboard)
            return {"status": "success", "api_key": existing_key, "tokens": tokens, "message": "Email already registered. Returned your active API key."}
        
        # Create new trial key
        new_key = f"mf_live_{secrets.token_hex(8)}"
        payload = {"id": new_key, "email": data.email, "tokens": 500, "has_used_trial": True}
        
        res = requests.post(f"{clean_url}/rest/v1/profiles", headers=headers, json=payload)
        if res.status_code in [200, 201]:
            admin_keyboard = {
                "inline_keyboard": [
                    [{"text": "⚡ Upgrade to Pro", "url": "https://t.me/"}],
                    [{"text": "🗑️ Delete Account", "callback_data": f"del_{new_key}"}]
                ]
            }
            send_telegram_alert(f"🎁 **New Free Trial Key Generated:**\n- Email: `{data.email}`\n- Key: `{new_key}`", admin_keyboard)
            return {"status": "success", "api_key": new_key, "tokens": 500, "message": "Free trial API key created successfully."}
        else:
            raise HTTPException(status_code=500, detail=f"Database Error: {res.text}")
            
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
        return {"tokens": user.get("tokens", 0), "email": user.get("email", "N/A")}
    raise HTTPException(status_code=404, detail="API Key not found")

# OxaPay Invoice Generation ($10 & $50 Plans)
@app.post("/v1/payments/create-invoice")
def create_oxapay_invoice(data: CheckoutRequest):
    plans_prices = {"pro": 10, "business": 50}
    if data.plan not in plans_prices:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")
        
    payload = {
        "merchant": OXAPAY_API_KEY,
        "amount": plans_prices[data.plan],
        "currency": "USD",
        "lifeTime": 60,
        "orderId": f"sub_{data.api_key}_{data.plan}",
        "email": data.email,
        "callbackUrl": f"{RENDER_EXTERNAL_URL}/v1/payments/webhook"
    }
    res = requests.post("https://api.oxapay.com/merchants/request", json=payload).json()
    if res.get("result") == 100:
        return {"status": "success", "payment_url": res.get("payLink")}
    raise HTTPException(status_code=400, detail="Failed to connect to OxaPay gateway.")

# Automatic Top-up Webhook
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
                
                admin_keyboard = {
                    "inline_keyboard": [
                        [{"text": "📊 Inspect Key Details", "callback_data": f"check_{api_key}"}]
                    ]
                }
                send_telegram_alert(f"💰 **Payment Confirmed & Account Recharged!**\n- API Key: `{api_key}`\n- Plan: `{plan.upper()}`\n- New Balance: `{curr + add_tokens}` Tokens", admin_keyboard)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/v1/feedback")
def receive_feedback(data: FeedbackRequest):
    admin_keyboard = {
        "inline_keyboard": [
            [{"text": "✉️ Reply to Customer", "url": "https://t.me/"}]
        ]
    }
    send_telegram_alert(f"📩 **New Support Ticket:**\n- Key: `{data.api_key}`\n- Message: {data.message}", admin_keyboard)
    return {"status": "success"}
