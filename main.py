import os
import requests
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import hmac
import hashlib

app = FastAPI(title="MediaFlow API", version="2.0")

# جلب الإعدادات ومتغيرات البيئة من Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OXAPAY_API_KEY = os.getenv("OXAPAY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # بوت التليجرام الخاص بك للإشعارات
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")      # معرف حسابك أو قناتك الخاصة بالأخطاء

# دالة إرسال التنبيهات الفورية لبوت التليجرام
def send_telegram_alert(message: str):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Failed to send telegram alert: {e}")

# نموذج بيانات إنشاء طلب الدفع (Checkout)
class CheckoutRequest(BaseModel):
    user_id: str
    plan: str  # "pro" ($10) or "business" ($50)
    email: str

# نموذج بيانات استقبال الملاحظات والمقترحات أو الأخطاء من المطورين
class FeedbackRequest(BaseModel):
    user_id: str
    feedback_type: str  # "bug", "suggestion", "other"
    message: str

# 1. نقطة إنشاء رابط الدفع الذاتي عبر OxaPay
@app.post("/v1/payments/create-invoice")
def create_oxapay_invoice(data: CheckoutRequest):
    plans = {
        "pro": {"amount": 10, "tokens": 10000, "title": "MediaFlow Pro Plan (10,000 Tokens)"},
        "business": {"amount": 50, "tokens": 70000, "title": "MediaFlow Business Plan (70,000 Tokens)"}
    }
    
    if data.plan not in plans:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")
    
    selected_plan = plans[data.plan]
    
    # إعدادات الطلب لمنصة OxaPay
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

# 2. نقطة استقبال الـ Webhook (شحن الرصيد أوتوماتيكياً عند إتمام الدفع)
@app.post("/v1/payments/webhook")
async def oxapay_webhook(request: Request):
    try:
        body = await request.json()
        
        # التحقق من نجاح عملية الدفع من OxaPay
        status = body.get("status")
        order_id = body.get("orderId")
        amount = body.get("amount")
        
        if status == "Complete" or status == 1:
            # استخراج معرف المستخدم والباقة من orderId (مثال: sub_USER_ID_pro)
            parts = order_id.split("_")
            user_id = parts[1]
            plan = parts[2]
            
            tokens_to_add = 10000 if plan == "pro" else 70000
            
            # هنا يتم تحديث رصيد المستخدم في قاعدة بيانات Supabase أوتوماتيكياً
            supabase_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            
            # جلب الرصيد الحالي أولاً ثم الإضافة عليه (أو عبر دالة RPC في سوبابيس)
            get_url = f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}"
            res = requests.get(get_url, headers=supabase_headers).json()
            
            if res:
                current_tokens = res[0].get("tokens", 0)
                new_tokens = current_tokens + tokens_to_add
                
                update_url = f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}"
                requests.patch(update_url, headers=supabase_headers, json={"tokens": new_tokens})
                
                # إرسال إشعار تفصيلي ناجح لك على التليجرام
                send_telegram_alert(f"💰 **عملية دفع ناجحة وشحن تلقائي!**\n- الباقة: {plan.upper()}\n- المبلغ: ${amount}\n- المستخدم: {user_id}\n- الرصيد الجديد: {new_tokens} Token")
            
        return {"status": "ok"}
    except Exception as e:
        send_telegram_alert(f"🚨 خطأ فادح في الـ Webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 3. خانة استقبال الملاحظات، الشكاوي، الأخطاء والمقترحات من المطورين
@app.post("/v1/feedback")
def receive_feedback(data: FeedbackRequest):
    try:
        alert_msg = f"📝 **ملاحظة/مشكلة جديدة من مطور:**\n- نوع المشاركة: {data.feedback_type.upper()}\n- معرف المستخدم: {data.user_id}\n- الرسالة: {data.message}"
        send_telegram_alert(alert_msg)
        return {"status": "success", "message": "Feedback received successfully. Thank you!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def home():
    return {"status": "MediaFlow API is running smoothly with automated OxaPay billing and Telegram alerts!"}
    
