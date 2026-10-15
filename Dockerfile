FROM python:3.10-slim

WORKDIR /app

# تثبيت المكتبات البرمجية
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملفات المشروع
COPY . .

EXPOSE 8000

# تشغيل السيرفر بأعلى أداء
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
