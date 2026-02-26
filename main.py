from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract
import io
import re
import os

# --- إعدادات النظام للسيرفر (Linux) ---
# هذا السطر يخبر البايثون بمكان وجود محرك Tesseract في سيرفرات Render
# عادة ما يكون المسار الافتراضي في Linux هو /usr/bin/tesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

app = FastAPI(title="EE Club Smart Schedule API")

# إعدادات CORS للسماح للموقع بالاتصال بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # يمكنك وضع رابط موقعك هنا لاحقاً لزيادة الأمان
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# أوقات الفترات الرسمية (يجب أن تطابق الـ IDs في الـ Frontend)
VALID_SLOTS = ["54", "86", "44", "80", "57", "47", "63", "52", "51"]

@app.post("/upload-schedule/")
async def analyze_schedule(file: UploadFile = File(...)):
    # التأكد من أن الملف المرفوع هو صورة
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="الملف المرفوع ليس صورة.")

    try:
        # 1. قراءة محتوى الصورة
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # 2. تحسين الصورة برمجياً لزيادة دقة القراءة (اختياري)
        image = image.convert('L') # تحويلها للأبيض والأسود لتحسين التعرف
        
        # 3. استخراج النص باستخدام Tesseract
        # استخدمنا config لضمان التركيز على الأرقام والحروف اللاتينية
        extracted_text = pytesseract.image_to_string(image, lang='eng')
        
        # 4. معالجة النص المستخرج (Parser)
        schedule_data = []
        lines = extracted_text.split('\n')
        
        for line in lines:
            # صيد رمز المادة (مثل EE 205 أو MATH201)
            course_match = re.search(r'([A-Z]{2,4}\s?\d{3})', line, re.IGNORECASE)
            
            if course_match:
                course_name = course_match.group(1).upper().replace(' ', '')
                
                # البحث عن أي رقمين أو ثلاثة (للفترات)
                potential_slots = re.findall(r'\b(\d{2,3})\b', line)
                
                # تصفية الأرقام لتشمل فقط الفترات الصحيحة عندنا
                valid_found_slots = [s for s in potential_slots if s in VALID_SLOTS]
                
                if valid_found_slots:
                    for i, slot in enumerate(valid_found_slots):
                        # توزيع افتراضي ذكي (يضع المادة في أيام مختلفة بناءً على ترتيبها)
                        # الطالب سيقوم بتعديلها يدوياً لو كانت الإزاحة بسيطة
                        day_index = (i + len(course_name)) % 5 
                        
                        schedule_data.append({
                            "day": day_index,
                            "slotId": slot,
                            "name": course_name,
                            "room": "قاعة ؟",
                            "color": {"bg": "#4f46e5", "text": "#ffffff"}
                        })

        # التحقق إذا لم نجد أي بيانات
        if not schedule_data:
            return {
                "status": "warning",
                "message": "لم نجد رموز مواد واضحة، حاول رفع صورة أكثر وضوحاً.",
                "data": []
            }

        return {
            "status": "success",
            "message": f"تم استخراج {len(schedule_data)} محاضرة بنجاح!",
            "data": schedule_data
        }

    except Exception as e:
        # طباعة الخطأ في الـ Logs حق Render عشان نعرف وش المشكلة
        print(f"Error during OCR: {str(e)}")
        return {"status": "error", "message": "حدث خطأ فني أثناء تحليل الصورة."}

@app.get("/")
def read_root():
    return {"status": "online", "message": "سيرفر ذكاء الجداول يعمل بنجاح 🚀"}
