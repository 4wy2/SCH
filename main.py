from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract
import io
import re
import pdfplumber

# إعداد مسار المحرك للسيرفر
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_SLOTS = ["54", "86", "44", "80", "57", "47", "63", "52", "51", "88", "84"]

def extract_schedule_logic(text):
    """خوارزمية استخراج المواد والأوقات من النص المستخرج"""
    results = []
    lines = text.split('\n')
    for line in lines:
        # البحث عن رمز المادة (مثل EE 202)
        course_match = re.search(r'([A-Z]{2,4}\s?\d{3})', line, re.IGNORECASE)
        if course_match:
            name = course_match.group(1).upper().replace(' ', '')
            # البحث عن أرقام الفترات المكونة من رقمين
            slots = re.findall(r'\b(\d{2})\b', line)
            valid_slots = [s for s in slots if s in VALID_SLOTS]
            
            for i, s in enumerate(valid_slots):
                results.append({
                    "day": i % 5, 
                    "slotId": s,
                    "name": name,
                    "room": "قاعة PDF",
                    "color": {"bg": "#4f46e5", "text": "#ffffff"}
                })
    return results

@app.post("/upload-schedule/")
async def analyze_schedule(file: UploadFile = File(...)):
    extracted_text = ""
    
    try:
        # الحالة الأولى: الملف PDF
        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(await file.read())) as pdf:
                for page in pdf.pages:
                    extracted_text += page.extract_text() + "\n"
        
        # الحالة الثانية: الملف صورة
        elif file.content_type.startswith("image/"):
            image = Image.open(io.BytesIO(await file.read())).convert('L')
            extracted_text = pytesseract.image_to_string(image, lang='eng')
        
        else:
            raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم")

        final_data = extract_schedule_logic(extracted_text)

        if not final_data:
            return {"status": "warning", "message": "لم نجد مواد، جرب نسخة الـ PDF الرسمية", "data": []}

        return {"status": "success", "data": final_data}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def home(): return {"status": "online"}
