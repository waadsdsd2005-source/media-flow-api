import os
import secrets
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="MediaFlow API", version="4.0")

# جلب الإعدادات ومتغيرات البيئة من Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OXAPAY_API_KEY = os.getenv("OXAPAY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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

class FeedbackRequest(BaseModel):
    api_key: str
    feedback_type: str
    message: str

# 1. واجهة الموقع الرئيسية (تصميم نظيف، سهل، ويولد المفتاح بضغطة زر وبدون تعقيد)
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MediaFlow API - معالجة الصور الذكية</title>
        <style>
            * { box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0b0f19; color: #f8fafc; margin: 0; padding: 20px; text-align: center; }
            .container { max-width: 1000px; margin: auto; padding: 30px 15px; }
            h1 { color: #38bdf8; font-size: 2.2em; margin-bottom: 5px; }
            .subtitle { color: #94a3b8; font-size: 1.1em; margin-bottom: 40px; }
            
            .pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 25px; margin-top: 20px; align-items: stretch; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 30px 20px; text-align: right; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3); display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.3s; }
            .card:hover { transform: translateY(-5px); }
            .card.featured { border-color: #38bdf8; background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); position: relative; }
            .badge { position: absolute; top: -12px; left: 20px; background: #38bdf8; color: #0b0f19; font-size: 0.8em; font-weight: bold; padding: 4px 12px; border-radius: 20px; }
            
            .card h3 { color: #38bdf8; margin-top: 0; font-size: 1.4em; }
            .price { font-size: 2em; font-weight: bold; color: #facc15; margin: 15px 0; }
            .price span { font-size: 0.5em; color: #94a3b8; }
            
            .features { list-style: none; padding: 0; margin: 20px 0; color: #cbd5e1; font-size: 0.95em; line-height: 1.8; flex-grow: 1; }
            .features li::before { content: "✓ "; color: #38bdf8; font-weight: bold; margin-left: 5px; }
            
            .btn { display: block; background: #2563eb; color: white; padding: 12px; text-align: center; border-radius: 8px; text-decoration: none; font-weight: bold; cursor: pointer; border: none; width: 100%; transition: background 0.3s; font-size: 1em; }
            .btn:hover { background: #1d4ed8; }
            .btn-free { background: #334155; color: #38bdf8; }
            .btn-free:hover { background: #475569; }
            
            /* صندوق عرض مفتاح الـ API */
            .key-box { background: #0f172a; border: 1px solid #38bdf8; border-radius: 12px; padding: 20px; margin-top: 30px; text-align: center; display: none; }
            .key-box input { width: 80%; padding: 10px; background: #1e293b; border: 1px solid #334155; color: #38bdf8; font-family: monospace; text-align: center; border-radius: 6px; font-size: 1.1em; margin-bottom: 10px; }
            
            .feedback-section { margin-top: 50px; background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 30px; text-align: right; max-width: 600px; margin-left: auto; margin-right: auto; }
            .feedback-section h3 { color: #38bdf8; margin-top: 0; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; color: #94a3b8; margin-bottom: 5px; font-size: 0.9em; }
            .form-control { width: 100%; padding: 10px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #fff; font-size: 1em; }
            textarea.form-control { resize: vertical; height: 100px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MediaFlow API</h1>
            <p class="subtitle">المنصة الأسرع والأكثر توفيراً للمطورين لمعالجة الصور والبيانات بدقة فائقة</p>

            <!-- صندوق ظهور المفتاح للمطور -->
            <div id="apiKeyContainer" class="key-box">
                <p style="color: #facc15; margin-top: 0; font-weight: bold;">🎉 مبروك! تم إنشاء حسابك ومفتاح الـ API الخاص بك بنجاح:</p>
                <input type="text" id="generatedApiKey" readonly>
                <button class="btn" style="background: #16a34a; width: 80%; margin: auto;" onclick="copyKey()">نسخ المفتاح واحتفظ به</button>
            </div>

            <div class="pricing-grid">
                <!-- 1. الباقة التجريبية -->
                <div class="card">
                    <div>
                        <h3>الباقة التجريبية</h3>
                        <div class="price">$0 <span>/ مجاناً</span></div>
                        <ul class="features">
                            <li>500 نقطة تجريبية (20 صورة)</li>
                            <li>توليد مفتاح API فوري</li>
                            <li>بدون تعقيد أو بطاقة دفع</li>
                            <li>تمنح مرة واحدة لكل بريد</li>
                        </ul>
                    </div>
                    <button class="btn btn-free" onclick="getFreeTrial()">احصل على مفتاحك المجاني</button>
                </div>

                <!-- 2. الباقة الاحترافية Pro -->
                <div class="card featured">
                    <div class="badge">الأكثر طلباً</div>
                    <div>
                        <h3>الباقة الاحترافية (Pro)</h3>
                        <div class="price">$10 <span>/ شهرياً</span></div>
                        <ul class="features">
                            <li>10,000 نقطة (Token)</li>
                            <li>معالجة فائقة السرعة للصور</li>
                            <li>دعم كافة صيغ الوسائط</li>
                            <li>دعم فني مخصص للمطورين</li>
                        </ul>
                    </div>
                    <button class="btn" onclick="subscribe('pro')">اشترك الآن</button>
                </div>

                <!-- 3. باقة الأعمال Business -->
                <div class="card">
                    <div>
                        <h3>باقة الأعمال (Business)</h3>
                        <div class="price">$50 <span>/ شهرياً</span></div>
                        <ul class="features">
                            <li>70,000 نقطة (Token)</li>
                            <li>أولوية قصوى في معالجة السيرفر</li>
                            <li>توفير كبير في التكاليف</li>
                            <li>دعم مباشر ومخصص للمشاريع</li>
                        </ul>
                    </div>
                    <button class="btn" style="background: #0284c7;" onclick="subscribe('business')">اشترك الآن</button>
                </div>
            </div>

            <!-- ركن الملاحظات والشكاوي -->
            <div class="feedback-section">
                <h3>💬 ركن المطورين (الملاحظات والأخطاء)</h3>
                <p style="color: #94a3b8; font-size: 0.9em; margin-bottom: 20px;">واجهتك مشكلة برمجية؟ أرسل لنا وسنستجيب فوراً.</p>
                <div class="form-group">
                    <label>مفتاح الـ API الخاص بك:</label>
                    <input type="text" id="fbApiKey" class="form-control" placeholder="أدخل مفتاح الـ API">
                </div>
                <div class="form-group">
                    <label>نوع المشاركة:</label>
                    <select id="fbType" class="form-control">
                        <option value="bug">بلاغ عن خطأ (Bug)</option>
                        <option value="suggestion">مقترح تطوير (Suggestion)</option>
                        <option value="other">ملاحظة عامة (Other)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>تفاصيل الرسالة:</label>
                    <textarea id="fbMessage" class="form-control" placeholder="اكتب ملاحظتك هنا..."></textarea>
                </div>
                <button class="btn" onclick="sendFeedback()">إرسال للإدارة</button>
            </div>
        </div>

        <script>
            async function getFreeTrial() {
                const email = prompt("أدخل بريدك الإلكتروني للحصول على مفتاح التجربة المجانية:");
                if (!email) return;

                try {
                    const response = await fetch('/v1/free-trial', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email: email })
                    });

                    const data = await response.json();
                    if (data.status === 'success') {
                        document.getElementById('generatedApiKey').value = data.api_key;
                        document.getElementById('apiKeyContainer').style.display = 'block';
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    } else {
                        alert("⚠️ " + data.detail);
                    }
                } catch (err) {
                    alert("خطأ في الاتصال بالسيرفر: " + err.message);
                }
            }

            function copyKey() {
                const keyInput = document.getElementById('generatedApiKey');
                keyInput.select();
                document.execCommand('copy');
                alert("تم نسخ المفتاح بنجاح! احتفظ به في مكان آمن.");
            }

            async function subscribe(plan) {
                const apiKey = prompt("أدخل مفتاح الـ API الخاص بك:");
                const email = prompt("أدخل بريدك الإلكتروني لإتمام الفاتورة عبر OxaPay:");
                
                if (!apiKey || !email) {
                    alert("الرجاء إدخال المفتاح والبريد الإلكتروني.");
                    return;
                }

                try {
                    const response = await fetch('/v1/payments/create-invoice', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: apiKey, plan: plan, email: email })
                    });

                    const data = await response.json();
                    if (data.status === 'success' && data.payment_url) {
                        window.location.href = data.payment_url;
                    } else {
                        alert("حدث خطأ أثناء إنشاء رابط الدفع.");
                    }
                } catch (err) {
                    alert("خطأ في الاتصال بالسيرفر: " + err.message);
                }
            }

            async function sendFeedback() {
                const apiKey = document.getElementById('fbApiKey').value;
                const feedbackType = document.getElementById('fbType').value;
                const message = document.getElementById('fbMessage').value;

                if (!apiKey || !message) {
                    alert("يرجى إدخال مفتاح الـ API ونَص الرسالة.");
                    return;
                }

                try {
                    const response = await fetch('/v1/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: apiKey, feedback_type: feedbackType, message: message })
                    });

                    const data = await response.json();
                    if (data.status === 'success') {
                        alert("شكراً لك! تم إرسال ملاحظتك بنجاح.");
                        document.getElementById('fbMessage').value = '';
                    } else {
                        alert("فشل في إرسال الملاحظة.");
                    }
                } catch (err) {
                    alert("حدث خطأ في الاتصال: " + err.message);
                }
            }
        </script>
    </body>
    </html>
    """

# 2. توليد مفتاح تجريبي مجاني أوتوماتيكياً بربط البريد الإلكتروني
@app.post("/v1/free-trial")
def activate_free_trial(data: FreeTrialRequest):
    supabase_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    get_url = f"{SUPABASE_URL}/rest/v1/profiles?email=eq.{data.email}"
    try:
        res = requests.get(get_url, headers=supabase_headers).json()
        
        if res:
            if res[0].get("has_used_trial", False):
                raise HTTPException(status_code=400, detail="هذا البريد استنفذ التجربة المجانية سابقاً.")
            
            api_key = res[0].get("api_key")
            current_tokens = res[0].get("tokens", 0)
            update_url = f"{SUPABASE_URL}/rest/v1/profiles?email=eq.{data.email}"
            requests.patch(update_url, headers=supabase_headers, json={"tokens": current_tokens + 500, "has_used_trial": True})
            
            return {"status": "success", "api_key": api_key, "message": "تم تفعيل التجربة وإضافة 500 نقطة لمفتاحك بنجاح!"}
        else:
            # توليد مفتاح API فريد للمطور تلقائياً
            new_api_key = f"mf_live_{secrets.token_hex(16)}"
            post_url = f"{SUPABASE_URL}/rest/v1/profiles"
            payload = {"api_key": new_api_key, "email": data.email, "tokens": 500, "has_used_trial": True}
            requests.post(post_url, headers=supabase_headers, json=payload)
            
            send_telegram_alert(f"🎁 **مطور جديد حصل على مفتاح تجريبي!**\n- البريد: `{data.email}`\n- المفتاح: `{new_api_key}`")
            return {"status": "success", "api_key": new_api_key, "message": "تم إنشاء المفتاح وتفعيل 500 نقطة تجريبية بنجاح!"}
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="حدث خطأ في النظام أثناء التفعيل.")

# 3. إنشاء رابط الدفع الذاتي عبر OxaPay
@app.post("/v1/payments/create-invoice")
def create_oxapay_invoice(data: CheckoutRequest):
    plans = {
        "pro": {"amount": 10, "tokens": 10000, "title": "MediaFlow Pro Plan (10,000 Tokens)"},
        "business": {"amount": 50, "tokens": 70000, "title": "MediaFlow Business Plan (70,000 Tokens)"}
    }
    
    if data.plan not in plans:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")
    
    selected_plan = plans[data.plan]
    
    payload = {
        "merchant": OXAPAY_API_KEY,
        "amount": selected_plan["amount"],
        "currency": "USD",
        "lifeTime": 60,
        "feePaidByPayer": 0,
        "orderId": f"sub_{data.api_key}_{data.plan}",
        "desc": selected_plan["title"],
        "email": data.email,
        "callbackUrl": "https://media-flow-api.onrender.com/v1/payments/webhook"
    }
    
    try:
        response = requests.post("https://api.oxapay.com/merchants/request", json=payload)
        res_data = response.json()
        
        if res_data.get("result") == 100:
            return {"status": "success", "payment_url": res_data.get("payLink")}
        else:
            send_telegram_alert(f"⚠️ خطأ في إنشاء فاتورة OxaPay: {res_data}")
            raise HTTPException(status_code=400, detail="Could not generate payment link.")
    except Exception as e:
        send_telegram_alert(f"🚨 استثناء برمجي في الدفع: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 4. استقبال الـ Webhook وشحن الرصيد تلقائياً عبر مفتاح الـ API
@app.post("/v1/payments/webhook")
async def oxapay_webhook(request: Request):
    try:
        body = await request.json()
        status = body.get("status")
        order_id = body.get("orderId")
        amount = body.get("amount")
        
        if status == "Complete" or status == 1:
            parts = order_id.split("_")
            api_key = parts[1]
            plan = parts[2]
            
            tokens_to_add = 10000 if plan == "pro" else 70000
            
            supabase_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            
            get_url = f"{SUPABASE_URL}/rest/v1/profiles?api_key=eq.{api_key}"
            res = requests.get(get_url, headers=supabase_headers).json()
            
            if res:
                current_tokens = res[0].get("tokens", 0)
                new_tokens = current_tokens + tokens_to_add
                
                update_url = f"{SUPABASE_URL}/rest/v1/profiles?api_key=eq.{api_key}"
                requests.patch(update_url, headers=supabase_headers, json={"tokens": new_tokens})
                
                send_telegram_alert(f"💰 **عملية دفع ناجحة وشحن تلقائي!**\n- الباقة: {plan.upper()}\n- المبلغ: ${amount}\n- المفتاح: `{api_key}`\n- الرصيد الجديد: {new_tokens} Token")
            
        return {"status": "ok"}
    except Exception as e:
        send_telegram_alert(f"🚨 خطأ فادح في الـ Webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 5. استقبال الملاحظات والمقترحات والأخطاء
@app.post("/v1/feedback")
def receive_feedback(data: FeedbackRequest):
    try:
        alert_msg = f"📝 **ملاحظة/مشكلة جديدة من مطور:**\n- النوع: {data.feedback_type.upper()}\n- المفتاح: `{data.api_key}`\n- الرسالة: {data.message}"
        send_telegram_alert(alert_msg)
        return {"status": "success", "message": "Feedback received successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
