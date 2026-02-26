from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract
import io
import re

# تهيئة السيرفر
app = FastAPI(title="EE Club Smart Schedule API")

# السماح للموقع بالاتصال بالسيرفر (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # في الإنتاج، تحط رابط موقعك هنا
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# الأوقات المعرفة في نظامكم
VALID_SLOTS = ["54", "86", "44", "80", "57", "47", "63", "52", "51"]

@app.post("/upload-schedule/")
async def analyze_schedule(file: UploadFile = File(...)):
    try:
        # 1. قراءة الصورة المرفوعة
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # 2. استخراج النص باستخدام الذكاء الاصطناعي
        # ملاحظة: تأكد من تثبيت Tesseract-OCR في جهازك
        extracted_text = pytesseract.image_to_string(image, lang='eng')
        
        # 3. خوارزمية تفكيك الجدول
        schedule_data = []
        lines = extracted_text.split('\n')
        
        for line in lines:
            # البحث عن رموز المواد (مثال: EE 205 أو MATH201)
            course_match = re.search(r'([A-Z]{2,4}\s?\d{3})', line, re.IGNORECASE)
            
            if course_match:
                course_name = course_match.group(1).upper().replace(' ', '')
                
                # البحث عن أرقام الأوقات (مثل 47, 63, 52)
                slots = re.findall(r'\b(\d{2})\b', line)
                
                # توزيع عشوائي (مسودة) للأوقات في أيام مختلفة إذا لقينا أوقات
                valid_found_slots = [s for s in slots if s in VALID_SLOTS]
                
                if valid_found_slots:
                    for i, slot in enumerate(valid_found_slots):
                        day_index = i % 5  # توزيع على الأيام (0 إلى 4)
                        schedule_data.append({
                            "day": day_index,
                            "slotId": slot,
                            "name": course_name,
                            "room": "قاعة؟", # يمكن تطويرها لاحقاً لاستخراج القاعة
                            "color": {"bg": "#4f46e5", "text": "#ffffff"} # لون افتراضي
                        })

        # 4. إرجاع البيانات للموقع
        return {
            "status": "success",
            "message": f"تم استخراج {len(schedule_data)} محاضرة بنجاح!",
            "data": schedule_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# مسار تجريبي للتأكد إن السيرفر شغال
@app.get("/")
def read_root():
    return {"message": "سيرفر نادي الهندسة الكهربائية يعمل بكفاءة 🚀"}
