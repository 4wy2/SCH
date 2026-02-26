from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract
import io
import re
import pdfplumber
import os

# إعداد مسار المحرك لنظام Linux على Render
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

app = FastAPI(title="EE Club AI Scheduler")

# السماح بالاتصال من أي مصدر (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# قائمة الفترات الرسمية بناءً على نظام الكلية
VALID_SLOTS = ["54", "86", "44", "80", "57", "47", "63", "52", "51", "88", "84"]

def extract_schedule_logic(text):
    """خوارزمية ذكية لاستخراج المواد وتوزيعها"""
    results = []
    # تنظيف النص من الفراغات الزائدة
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines:
        # البحث عن رمز المادة (مثل EE 202)
        course_match = re.search(r'([A-Z]{2,4}\s?\d{3})', line, re.IGNORECASE)
        if course_match:
            name = course_match.group(1).upper().replace(' ', '')
            
            # البحث عن أرقام الفترات المكونة من رقمين فقط
            slots = re.findall(r'\b(\d{2})\b', line)
            valid_slots = [s for s in slots if s in VALID_SLOTS]
            
            # توزيع افتراضي: نضع المحاضرات في أيام متتالية كمسودة
            for i, s in enumerate(valid_slots):
                results.append({
                    "day": i % 5, 
                    "slotId": s,
                    "name": name,
                    "room": "مستخرج تلقائياً",
                    "color": {"bg": "#4f46e5", "text": "#ffffff"}
                })
    return results

@app.post("/upload-schedule/")
async def analyze_schedule(file: UploadFile = File(...)):
    extracted_text = ""
    try:
        # 1. إذا كان الملف PDF (الدقة الأعلى)
        if file.content_type == "application/pdf":
            pdf_content = await file.read()
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    extracted_text += page.extract_text() + "\n"
        
        # 2. إذا كان الملف صورة (استخدام OCR)
        elif file.content_type.startswith("image/"):
            image_content = await file.read()
            image = Image.open(io.BytesIO(image_content)).convert('L')
            extracted_text = pytesseract.image_to_string(image, lang='eng')
        
        else:
            raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم. يرجى رفع صورة أو PDF.")

        # 3. معالجة النص المستخرج
        final_data = extract_schedule_logic(extracted_text)

        if not final_data:
            return {
                "status": "warning", 
                "message": "نجحنا في قراءة الملف لكن لم نجد مواد واضحة. تأكد أن الملف يحتوي على جدولك الدراسي.",
                "data": []
            }

        return {
            "status": "success",
            "message": f"تم استخراج {len(final_data)} محاضرة بنجاح!",
            "data": final_data
        }

    except Exception as e:
        print(f"Server Error: {str(e)}")
        return {"status": "error", "message": "حدث خطأ فني أثناء المعالجة."}

@app.get("/")
def home():
    return {"status": "online", "service": "EE Smart Scheduler API"}
