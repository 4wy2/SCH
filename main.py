from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import io
import re

app = FastAPI()

# تفعيل الـ CORS لضمان اتصال المتصفح بالسيرفر بدون مشاكل
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# تعريف أوقات الفترات الرسمية بناءً على الجدول المرفق 
PERIODS_MAP = {
    "44": "09:15-10:05", "47": "12:15-13:05", "51": "15:15-16:05",
    "52": "14:15-15:05", "54": "07:15-08:05", "57": "11:15-12:05",
    "63": "13:15-14:05", "80": "10:15-11:05", "86": "08:15-09:05"
}

def clean_and_parse(text):
    results = []
    lines = text.split('\n')
    
    # نمط البحث عن رموز المواد (حرفين ثم مسافة اختيارية ثم 3 أرقام) 
    course_pattern = r'([A-Z]{2,3}\s?\d{3})'
    
    for line in lines:
        # البحث عن رمز المادة في السطر
        match = re.search(course_pattern, line)
        if match:
            course_code = match.group(1).replace(" ", "")
            
            # استخراج كافة أرقام الفترات المكونة من خانتين والموجودة في القائمة الرسمية 
            # نستخدم regex يبحث عن الأرقام المعرفة في PERIODS_MAP
            found_slots = re.findall(r'\b(44|47|51|52|54|57|63|80|86)\b', line)
            
            if found_slots:
                # توزيع الفترات المستخرجة على الأيام بناءً على موقعها في السطر
                # في جداول الهيئة، الترتيب هو: الأحد، الاثنين، الثلاثاء، الأربعاء، الخميس 
                for idx, slot in enumerate(found_slots):
                    # نحدد اليوم بشكل تقريبي بناءً على ترتيب الظهور في السطر المنسوخ
                    results.append({
                        "day": idx % 5, 
                        "slotId": slot,
                        "name": course_code,
                        "room": "RC-Building", # يمكن تطوير استخراج القاعة لاحقاً
                        "color": {"bg": "#1e40af", "text": "#ffffff"}
                    })
    return results

@app.post("/upload-schedule/")
async def analyze_schedule(file: UploadFile = File(...)):
    try:
        content = await file.read()
        extracted_text = ""
        
        # تحليل ملفات الـ PDF (الدقة الأعلى للملف المرفق)
        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    extracted_text += page.extract_text() + "\n"
        
        data = clean_and_parse(extracted_text)
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def health(): return {"status": "online"}
