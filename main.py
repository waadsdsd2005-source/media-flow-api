import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="MediaFlow API", version="2.0")

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
    user_id: str
    plan: str
    email: str

class FeedbackRequest(BaseModel):
    user_id: str
    feedback_type: str
    message: str

# 1. واجهة الموقع الرئيسية (HTML) لتظهر للمطورين مباشرة عند فتح الرابط
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
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; margin: 0; padding: 20px; text-align: center; }
            .container { max-width: 900px; margin: auto; padding: 40px 20px; }
            h1 { color: #38bdf8; margin-bottom: 10px; }
            p { color: #94a3b8; font-size: 1.1em; }
            .pricing-grid { display: flex; justify-content: center; gap: 20px; margin-top: 40px; flex-wrap: wrap; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 30px; width: 280px; text-align: right; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .card h3 { color: #38bdf8; margin-top: 0; }
            .price { font-size: 1.8em; font-weight: bold; color: #facc15; margin: 15px 0; }
            .features { list-style: none; padding: 0; margin: 20px 0; color: #cbd5e1; font-size: 0.9em; line-height: 1.6; }
            .btn { display: block; background: #2563eb; color: white; padding: 12px; text-align: center; border-radius: 6px; text-decoration: none; font-weight: bold; cursor: pointer; border: none; width: 100%; transition: background 0.3s; }
            .btn:hover { background: #1d4ed8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MediaFlow API</h1>
            <p>الحل الأمثل للمطورين لمعالجة وضغط الصور بسرعة فائقة وتوفير استهلاك الـ Tokens.</p>

            <div class="pricing-grid">
                <!-- الباقة الاحترافية -->
                <div class="card">
                    <h3>الباقة الاحترافية (Pro)</h3>
                    <div class="price">$10</div>
                    <ul class="features">
                        <li>✔️ 10,000 نقطة (Token)</li>
                        <li>✔️ معالجة سريعة للصور</li>
                        <li>✔️ دعم كافة الصيغ</li>
                        <li>✔️ دعم فني للمطورين</li>
                    </ul>
                    <button class="btn" onclick="subscribe('pro')">اشترك الآن</button>
                </div>

                <!-- باقة الأعمال -->
                <div class="card" style="border-color: #38bdf8;">
                    <h3>باقة الأعمال (Business)</h3>
                    <div class="price">$50</div>
                    <ul class="features">
                        <li>✔️ 70,000 نقطة (Token)</li>
                        <li>✔️ أولوية قصوى في السيرفر</li>
                        <li>✔️ دعم مباشر ومخصص</li>
                        <li>✔️ توفير عالي للتكاليف</li>
                    </ul>
                    <button class="btn" style="background: #0284c7;" onclick="subscribe('business')">اشترك الآن</button>
                </div>
            </div>
        </div>

        <script>
            async function subscribe(plan) {
                const userId = prompt("أدخل معرف المستخدم الخاص بك (User ID):");
                const email = prompt("أدخل بريدك الإلكتروني لإتمام الفاتورة:");
                
                if (!userId || !email) {
                    alert("الرجاء إدخال المعرف والبريد الإلكتروني.");
                    return;
                }

                try {
                    const response = await fetch('/v1/payments/create-invoice', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: userId, plan: plan, email: email })
                    });

                    const data = await response.json();
                    if (data.status === 'success' && data.payment_url) {
                        window.location.href = data.payment_url;
                    } else {
                        alert("حدث خطأ أثناء إنشاء رابط الدفع. حاول مرة أخرى.");
                    }
                } catch (err) {
                    alert("خطأ في الاتصال بالسيرفر: " + err.message);
                }
            }
        </script>
    </body>
    </html>
    """

# 2. إنشاء رابط الدفع الذاتي عبر OxaPay
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
        "orderId": f"sub_{data.user_id}_{data.plan}",
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

# 3. استقبال الـ Webhook (شحن الرصيد تلقائياً عند الدفع)
@app.post("/v1/payments/webhook")
async def oxapay_webhook(request: Request):
    try:
        body = await request.json()
        status = body.get("status")
        order_id = body.get("orderId")
        amount = body.get("amount")
        
        if status == "Complete" or status == 1:
            parts = order_id.split("_")
            user_id = parts[1]
            plan = parts[2]
            
            tokens_to_add = 10000 if plan == "pro" else 70000
            
            supabase_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            
            get_url = f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}"
            res = requests.get(get_url, headers=supabase_headers).json()
            
            if res:
                current_tokens = res[0].get("tokens", 0)
                new_tokens = current_tokens + tokens_to_add
                
                update_url = f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}"
                requests.patch(update_url, headers=supabase_headers, json={"tokens": new_tokens})
                
                send_telegram_alert(f"💰 **عملية دفع ناجحة وشحن تلقائي!**\n- الباقة: {plan.upper()}\n- المبلغ: ${amount}\n- المستخدم: {user_id}\n- الرصيد الجديد: {new_tokens} Token")
            
        return {"status": "ok"}
    except Exception as e:
        send_telegram_alert(f"🚨 خطأ فادح في الـ Webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 4. خانة استقبال الملاحظات، الأخطاء، والمقترحات
@app.post("/v1/feedback")
def receive_feedback(data: FeedbackRequest):
    try:
        alert_msg = f"📝 **ملاحظة/مشكلة جديدة من مطور:**\n- النوع: {data.feedback_type.upper()}\n- المستخدم: {data.user_id}\n- الرسالة: {data.message}"
        send_telegram_alert(alert_msg)
        return {"status": "success", "message": "Feedback received successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
