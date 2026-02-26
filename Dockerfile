# 1. استخدام نسخة بايثون رسمية وخفيفة
FROM python:3.10-slim

# 2. السحر هنا: تثبيت محرك الذكاء الاصطناعي لقراءة الصور (Tesseract)
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 3. تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# 4. نسخ ملفات المشروع وتثبيت مكتبات البايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 5. تشغيل سيرفر FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
