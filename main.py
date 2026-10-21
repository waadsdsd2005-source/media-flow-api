import os
import secrets
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="MediaFlow API", version="6.0")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OXAPAY_API_KEY = os.getenv("OXAPAY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MediaFlow API - منصة المطورين</title>
        <style>
            * { box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0b0f19; color: #f8fafc; margin: 0; padding: 20px; text-align: center; }
            .container { max-width: 900px; margin: auto; padding: 20px; }
            h1 { color: #38bdf8; font-size: 2.2em; margin-bottom: 5px; }
            .subtitle { color: #94a3b8; font-size: 1.1em; margin-bottom: 30px; }
            .dash-card, .card { background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 25px; margin-bottom: 25px; text-align: right; }
            .dash-card { border-color: #38bdf8; }
            .pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; }
            .price { font-size: 1.8em; font-weight: bold; color: #facc15; margin: 10px 0; }
            .features { list-style: none; padding: 0; margin: 15px 0; color: #cbd5e1; font-size: 0.9em; line-height: 1.6; }
            .features li::before { content: "✓ "; color: #38bdf8; font-weight: bold; }
            .input-group { margin-bottom: 12px; }
            .input-group input { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #fff; text-align: right; font-size: 1em; }
            .btn { display: block; background: #2563eb; color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; cursor: pointer; border: none; width: 100%; font-size: 1em; transition: background 0.3s; }
            .btn:hover { background: #1d4ed8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MediaFlow API</h1>
            <p class="subtitle">منصة المطورين لمعالجة الوسائط والأتمتة الذكية</p>

            <!-- فحص الرصيد -->
            <div class="dash-card">
                <h3 style="color: #38bdf8; margin-top:0;">🔍 لوحة فحص رصيد المفتاح</h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <input type="text" id="checkApiKey" style="flex: 1; min-width: 200px;" placeholder="أدخل مفتاحك (mf_live_...)">
                    <button class="btn" style="width: 140px;" onclick="checkBalance()">فحص الرصيد</button>
                </div>
                <div id="balanceResult" style="display: none; background: #0f172a; padding: 12px; border-radius: 8px; margin-top: 12px; color: #38bdf8;"></div>
            </div>

            <div class="pricing-grid">
                <!-- الباقة المجانية -->
                <div class="card">
                    <h3 style="color:#38bdf8; margin-top:0;">الباقة التجريبية</h3>
                    <div class="price">$0 <span style="font-size:0.5em; color:#94a3b8;">/ مجاناً</span></div>
                    <ul class="features">
                        <li>توليد مفتاح API فوري</li>
                        <li>500 نقطة تجريبية مجانية</li>
                    </ul>
                    <div class="input-group" style="margin-top: 15px;">
                        <input type="email" id="freeEmail" placeholder="بريدك الإلكتروني">
                    </div>
                    <button class="btn" style="background:#334155; color:#38bdf8;" onclick="getFreeTrial()">إنشاء مفتاح مجاني</button>
                </div>

                <!-- باقة Pro -->
                <div class="card" style="border-color: #38bdf8;">
                    <h3 style="color:#38bdf8; margin-top:0;">الباقة الاحترافية (Pro)</h3>
                    <div class="price">$10 <span style="font-size:0.5em; color:#94a3b8;">/ شهرياً</span></div>
                    <ul class="features">
                        <li>10,000 نقطة (Token)</li>
                        <li>شحن مباشر لمفتاحك</li>
                    </ul>
                    <button class="btn" style="margin-top: 35px;" onclick="subscribe('pro')">اشترك الآن</button>
                </div>
            </div>
        </div>

        <script>
            async function getFreeTrial() {
                const email = document.getElementById('freeEmail').value.trim();
                if (!email) { alert("يرجى إدخال البريد الإلكتروني."); return; }

                try {
                    const res = await fetch('/v1/free-trial', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email: email })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        prompt("🎉 مبروك! تم إنشاء مفتاحك بنجاح. انسخه واحتفظ به:", data.api_key);
                        document.getElementById('checkApiKey').value = data.api_key;
                        checkBalance();
                    } else {
                        alert("⚠️ " + (data.detail || "حدث خطأ."));
                    }
                } catch(e) { alert("خطأ اتصال: " + e.message); }
            }

            async function checkBalance() {
                const apiKey = document.getElementById('checkApiKey').value.trim();
                if (!apiKey) { alert("أدخل مفتاح الـ API أولاً."); return; }

                try {
                    const res = await fetch('/v1/check-balance', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: apiKey })
                    });
                    const data = await res.json();
                    const box = document.getElementById('balanceResult');
                    box.style.display = 'block';
                    if (res.ok) {
                        box.innerHTML = "✨ <b>الرصيد المتبقي:</b> " + data.tokens + " Token<br>📧 <b>البريد:</b> " + data.email;
                    } else {
                        box.innerHTML = "<span style='color:#ef4444;'>⚠️ " + (data.detail || "المفتاح غير موجود") + "</span>";
                    }
                } catch(e) { alert("خطأ اتصال: " + e.message); }
            }

            async function subscribe(plan) {
                const apiKey = prompt("أدخل مفتاح الـ API الخاص بك لشحنه:");
                const email = prompt("أدخل بريدك الإلكتروني للفاتورة:");
                if (!apiKey || !email) return;

                try {
                    const res = await fetch('/v1/payments/create-invoice', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: apiKey, plan: plan, email: email })
                    });
                    const data = await res.json();
                    if (res.ok && data.payment_url) {
                        window.location.href = data.payment_url;
                    } else {
                        alert("خطأ في الدفع: " + (data.detail || "فشل إنشاء الرابط"));
                    }
                } catch(e) { alert("خطأ اتصال: " + e.message); }
            }
        </script>
    </body>
    </html>
    """

@app.post("/v1/free-trial")
def activate_free_trial(data: FreeTrialRequest):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="إعدادات Supabase غير مكتملة في Render.")
    
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    clean_url = SUPABASE_URL.strip().rstrip('/')
    
    try:
        new_key = f"mf_live_{secrets.token_hex(8)}"
        payload = {"id": new_key, "email": data.email, "tokens": 500, "has_used_trial": True}
        
        res = requests.post(f"{clean_url}/rest/v1/profiles", headers=headers, json=payload)
        if res.status_code in [200, 201]:
            send_telegram_alert(f"🎁 **مفتاح جديد مولّد:**\n- `{new_key}`\n- البريد: `{data.email}`")
            return {"status": "success", "api_key": new_key, "tokens": 500}
        else:
            raise HTTPException(status_code=500, detail=f"قاعدة البيانات رفضت الطلب: {res.text}")
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
        "callbackUrl": "https://media-flow-api.onrender.com/v1/payments/webhook"
    }
    res = requests.post("https://api.oxapay.com/merchants/request", json=payload).json()
    if res.get("result") == 100:
        return {"status": "success", "payment_url": res.get("payLink")}
    raise HTTPException(status_code=400, detail="فشل الاتصال ببوابة الدفع OxaPay.")
