import os
import secrets
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="MediaFlow API", version="5.0")

# جلب متغيرات البيئة من Render
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
            print(f"Failed to send telegram alert: {e}")

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
            .container { max-width: 1000px; margin: auto; padding: 30px 15px; }
            h1 { color: #38bdf8; font-size: 2.2em; margin-bottom: 5px; }
            .subtitle { color: #94a3b8; font-size: 1.1em; margin-bottom: 30px; }
            
            /* لوحة فحص الرصيد والمفتاح */
            .dash-card { background: #1e293b; border: 1px solid #38bdf8; border-radius: 16px; padding: 25px; margin-bottom: 40px; text-align: right; }
            .dash-card h3 { color: #38bdf8; margin-top: 0; }
            .key-display { background: #0f172a; border: 1px solid #334155; padding: 12px; border-radius: 8px; color: #facc15; font-family: monospace; font-size: 1.1em; text-align: center; word-break: break-all; margin: 10px 0; }
            
            .pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 25px; margin-top: 20px; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 30px 20px; text-align: right; display: flex; flex-direction: column; justify-content: space-between; }
            .card.featured { border-color: #38bdf8; background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); position: relative; }
            .badge { position: absolute; top: -12px; left: 20px; background: #38bdf8; color: #0b0f19; font-size: 0.8em; font-weight: bold; padding: 4px 12px; border-radius: 20px; }
            
            .price { font-size: 2em; font-weight: bold; color: #facc15; margin: 15px 0; }
            .features { list-style: none; padding: 0; margin: 20px 0; color: #cbd5e1; font-size: 0.95em; line-height: 1.8; }
            .features li::before { content: "✓ "; color: #38bdf8; font-weight: bold; }
            
            .input-group { margin-bottom: 12px; }
            .input-group input { width: 100%; padding: 10px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #fff; text-align: right; }
            .btn { display: block; background: #2563eb; color: white; padding: 12px; text-align: center; border-radius: 8px; text-decoration: none; font-weight: bold; cursor: pointer; border: none; width: 100%; font-size: 1em; }
            .btn:hover { background: #1d4ed8; }
            
            .feedback-section { margin-top: 50px; background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 30px; text-align: right; max-width: 600px; margin: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MediaFlow API</h1>
            <p class="subtitle">منصة المطورين لمعالجة الوسائط والأتمتة الذكية</p>

            <!-- لوحة التحكم وفحص الرصيد -->
            <div class="dash-card">
                <h3>🔍 لوحة تحكم المطورين (فحص الرصيد والمفتاح)</h3>
                <p style="color: #94a3b8; font-size: 0.9em;">أدخل مفتاح الـ API الخاص بك لمعرفة رصيدك المتبقي وحالة اشتراكك:</p>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <input type="text" id="checkApiKey" style="flex: 1; padding: 10px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #fff;" placeholder="أدخل مفتاحك هنا (مثال: mf_live_...)">
                    <button class="btn" style="width: 150px;" onclick="checkBalance()">فحص الرصيد</button>
                </div>
                <div id="balanceResult" style="display: none; background: #0f172a; padding: 15px; border-radius: 8px; margin-top: 10px; border-right: 4px solid #38bdf8;"></div>
            </div>

            <div class="pricing-grid">
                <!-- الباقة المجانية -->
                <div class="card">
                    <div>
                        <h3 style="color:#38bdf8;">الباقة التجريبية</h3>
                        <div class="price">$0 <span>/ مجاناً</span></div>
                        <ul class="features">
                            <li>توليد مفتاح API خاص فوراً</li>
                            <li>500 نقطة تجريبية مجانية</li>
                            <li>بدون بطاقة دفع أو تعقيد</li>
                        </ul>
                    </div>
                    <div>
                        <div class="input-group">
                            <input type="email" id="freeEmail" placeholder="أدخل بريدك الإلكتروني">
                        </div>
                        <button class="btn" style="background:#334155; color:#38bdf8;" onclick="getFreeTrial()">إنشاء مفتاح مجاني</button>
                    </div>
                </div>

                <!-- باقة Pro -->
                <div class="card featured">
                    <div class="badge">الأكثر طلباً</div>
                    <div>
                        <h3 style="color:#38bdf8;">الباقة الاحترافية (Pro)</h3>
                        <div class="price">$10 <span>/ شهرياً</span></div>
                        <ul class="features">
                            <li>10,000 نقطة (Token)</li>
                            <li>شحن مباشر لمفتاحك الحالي</li>
                            <li>معالجة فائقة السرعة للصور</li>
                            <li>دعم فني مخصص للمطورين</li>
                        </ul>
                    </div>
                    <button class="btn" onclick="subscribe('pro')">اشترك وشحن المفتاح</button>
                </div>

                <!-- باقة Business -->
                <div class="card">
                    <div>
                        <h3 style="color:#38bdf8;">باقة الأعمال (Business)</h3>
                        <div class="price">$50 <span>/ شهرياً</span></div>
                        <ul class="features">
                            <li>70,000 نقطة (Token)</li>
                            <li>أولوية قصوى في سيرفرات المعالجة</li>
                            <li>دعم مباشر للمشاريع الكبيرة</li>
                        </ul>
                    </div>
                    <button class="btn" style="background: #0284c7;" onclick="subscribe('business')">اشترك وشحن المفتاح</button>
                </div>
            </div>

            <!-- ركن الملاحظات -->
            <div class="feedback-section">
                <h3 style="color:#38bdf8;">💬 الدعم الفني والملاحظات</h3>
                <div class="input-group">
                    <input type="text" id="fbKey" placeholder="مفتاح الـ API الخاص بك">
                </div>
                <div class="input-group">
                    <textarea id="fbMsg" style="width:100%; height:80px; background:#0f172a; border:1px solid #334155; border-radius:6px; color:#fff; padding:10px;" placeholder="اكتب ملاحظتك أو مشكلتك..."></textarea>
                </div>
                <button class="btn" onclick="sendFeedback()">إرسال للدعم</button>
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
                        alert("🎉 تم إنشاء مفتاحك المجاني بنجاح:\n\n" + data.api_key + "\n\nاحفظ هذا المفتاح لتستخدمه في تطبيقاتك!");
                        document.getElementById('checkApiKey').value = data.api_key;
                        checkBalance();
                    } else {
                        alert("⚠️ " + (data.detail || "حدث خطأ."));
                    }
                } catch(e) { alert("خطأ بالاتصال: " + e.message); }
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
                        box.innerHTML = "✨ <b>الرصيد المتبقي:</b> " + data.tokens + " Token<br>📧 <b>البريد المرتبط:</b> " + data.email;
                    } else {
                        box.innerHTML = "<span style='color:#ef4444;'>⚠️ " + (data.detail || "المفتاح غير موجود") + "</span>";
                    }
                } catch(e) { alert("خطأ بالاتصال: " + e.message); }
            }

            async function subscribe(plan) {
                const apiKey = prompt("أدخل مفتاح الـ API الخاص بك الذي تريد شحنه:");
                const email = prompt("أدخل بريدك الإلكتروني لإتمام الفاتورة:");
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
                        alert("حدث خطأ أثناء إنشاء رابط الدفع.");
                    }
                } catch(e) { alert("خطأ بالاتصال: " + e.message); }
            }

            async function sendFeedback() {
                const key = document.getElementById('fbKey').value.trim();
                const msg = document.getElementById('fbMsg').value.trim();
                if (!key || !msg) { alert("يرجى ملء جميع الحقول."); return; }

                try {
                    const res = await fetch('/v1/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: key, feedback_type: 'general', message: msg })
                    });
                    if (res.ok) { alert("تم إرسال رسالتك بنجاح!"); document.getElementById('fbMsg').value = ''; }
                } catch(e) { alert("خطأ بالاتصال: " + e.message); }
            }
        </script>
    </body>
    </html>
    """

@app.post("/v1/free-trial")
def activate_free_trial(data: FreeTrialRequest):
    supabase_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    clean_url = SUPABASE_URL.strip().rstrip('/')
    get_url = f"{clean_url}/rest/v1/profiles?id=eq.{data.email}"
    
    try:
        res = requests.get(get_url, headers=supabase_headers)
        if res.status_code == 200 and res.json():
            user = res.json()[0]
            return {"status": "success", "api_key": user.get("id"), "tokens": user.get("tokens")}
        
        # إنشاء مفتاح جديد وحفظه
        new_key = f"mf_live_{secrets.token_hex(8)}"
        post_url = f"{clean_url}/rest/v1/profiles"
        payload = {"id": new_key, "tokens": 500, "has_used_trial": True}
        
        post_res = requests.post(post_url, headers=supabase_headers, json=payload)
        if post_res.status_code in [200, 201]:
            send_telegram_alert(f"🎁 **مفتاح جديد مولّد تلقائياً!**\n- المفتاح: `{new_key}`\n- البريد: `{data.email}`")
            return {"status": "success", "api_key": new_key, "tokens": 500}
        else:
            raise HTTPException(status_code=500, detail="فشل إنشاء المفتاح في قاعدة البيانات.")
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/check-balance")
def check_balance(data: CheckBalanceRequest):
    supabase_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    clean_url = SUPABASE_URL.strip().rstrip('/')
    get_url = f"{clean_url}/rest/v1/profiles?id=eq.{data.api_key}"
    
    res = requests.get(get_url, headers=supabase_headers)
    if res.status_code == 200 and res.json():
        user = res.json()[0]
        return {"tokens": user.get("tokens", 0), "email": "مرتبط بالمفتاح"}
    raise HTTPException(status_code=404, detail="المفتاح غير موجود في النظام.")

@app.post("/v1/payments/create-invoice")
def create_oxapay_invoice(data: CheckoutRequest):
    plans = {"pro": 10, "business": 50}
    if data.plan not in plans: raise HTTPException(status_code=400, detail="باقة غير صالحة.")
    
    payload = {
        "merchant": OXAPAY_API_KEY,
        "amount": plans[data.plan],
        "currency": "USD",
        "lifeTime": 60,
        "orderId": f"sub_{data.api_key}_{data.plan}",
        "email": data.email,
        "callbackUrl": "https://media-flow-api.onrender.com/v1/payments/webhook"
    }
    res = requests.post("https://api.oxapay.com/merchants/request", json=payload).json()
    if res.get("result") == 100:
        return {"status": "success", "payment_url": res.get("payLink")}
    raise HTTPException(status_code=400, detail="فشل إنشاء رابط الدفع.")

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
                send_telegram_alert(f"💰 **تم الدفع والشحن تلقائياً!**\n- المفتاح: `{api_key}`\n- الرصيد الجديد: {curr + add_tokens}")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/v1/feedback")
def receive_feedback(data: FeedbackRequest):
    send_telegram_alert(f"📝 **ملاحظة من مطور:**\n- المفتاح: `{data.api_key}`\n- الرسالة: {data.message}")
    return {"status": "success"}
    
