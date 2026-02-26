from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance
import io
import re

app = FastAPI()

# إعدادات الـ CORS للسماح للموقع بالاتصال بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# الفترات الرسمية في الهيئة الملكية
VALID_SLOTS = ["44", "47", "51", "52", "54", "57", "63", "80", "86"]

# ==========================================
# 1. دالة معالجة الـ PDF (دقة 100%)
# ==========================================
def parse_rcjy_table(table):
    results = []
    if not table: return results
    for row in table:
        # درع حماية: تجاهل الصفوف الفارغة أو التي لا تحتوي أعمدة كافية
        if not row or len(row) < 12: continue
        row_str = str(row[0] or "")
        if "Course Code" in row_str or "Total" in row_str: continue

        # معالجة الخلايا المتداخلة
        split_cells = [str(cell).split('\n') if cell else [""] for cell in row]
        num_entries = max(len(cell) for cell in split_cells)

        for i in range(num_entries):
            course_col = split_cells[0]
            course_code = course_col[i].strip() if i < len(course_col) else course_col[-1].strip()

            # التأكد أن النص هو رمز مادة هندسية أو عامة حقيقي
            if not re.search(r'[A-Za-z]{2,4}\s?\d{3}', course_code): continue
            course_name_clean = course_code.replace(" ", "").upper()

            # حماية الكود من الانهيار إذا اختلفت الأعمدة (تحديد القاعة)
            room = "TBA"
            if len(split_cells) > 13:
                room_col = split_cells[13]
                room = room_col[i].strip() if i < len(room_col) else room_col[-1].strip()
            elif len(split_cells) > 12:
                room_col = split_cells[12]
                room = room_col[i].strip() if i < len(room_col) else room_col[-1].strip()

            # البحث في أيام الأسبوع (من الأحد للخميس)
            for day_idx in range(7, 12):
                if day_idx >= len(split_cells): break
                day_col = split_cells[day_idx]
                day_content = day_col[i] if i < len(day_col) else day_col[-1]
                
                # استخراج أرقام الفترات
                if day_content:
                    slots = re.findall(r'\b(44|47|51|52|54|57|63|80|86)\b', day_content)
                    for s in slots:
                        results.append({
                            "day": day_idx - 7, 
                            "slotId": s, 
                            "name": course_name_clean, 
                            "room": room
                        })
    return results

# ==========================================
# 2. دالة معالجة الصور (مسودة ذكية)
# ==========================================
def parse_image(image_bytes):
    results = []
    try:
        # تحسين الصورة لتسهيل القراءة على الذكاء الاصطناعي
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        img = ImageEnhance.Contrast(img).enhance(2.0)
        text = pytesseract.image_to_string(img)
        
        # استخراج كل رموز المواد الموجودة في الصورة
        courses_found = re.findall(r'[A-Za-z]{2,4}\s?\d{3}', text)
        
        # تنظيف الرموز وإزالة التكرار (مثال: EE 204 تصبح EE204)
        unique_courses = list(set([c.replace(" ", "").upper() for c in courses_found]))
        
        if not unique_courses:
            return [] # لم يجد أي مادة
            
        # إذا وجد مواد، سيقوم برصها كـ "مسودة" في الجدول
        default_slots = ["54", "86", "44", "80", "57", "47", "63", "52", "51"]
        
        for idx, course in enumerate(unique_courses):
            # اختيار وقت عشوائي من القائمة
            slot = default_slots[idx % len(default_slots)]
            
            # إضافة المادة كمسودة (يضعها يوم الأحد والثلاثاء كبداية)
            results.append({
                "day": 0, # الأحد
                "slotId": slot,
                "name": course,
                "room": "مسودة-عدل الوقت"
            })
            results.append({
                "day": 2, # الثلاثاء
                "slotId": slot,
                "name": course,
                "room": "مسودة-عدل الوقت"
            })

    except Exception as e:
        print("Image OCR Error:", e)
        
    return results

# ==========================================
# 3. مسار الرفع الشامل (Endpoint)
# ==========================================
@app.post("/upload-schedule/")
async def upload_schedule(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # إذا كان الملف PDF
        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                table = pdf.pages[0].extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
                data = parse_rcjy_table(table)
                if not data: return {"status": "error", "message": "لم يتم العثور على مواد. تأكد من أن الملف هو جدول الإيدوقيت الأصلي."}
                return {"status": "success", "data": data, "type": "pdf"}
                
        # إذا كان الملف صورة
        elif file.content_type.startswith("image/"):
            data = parse_image(content)
            if not data: return {"status": "error", "message": "لم نتمكن من قراءة الصورة. تأكد أنها واضحة ومقصوصة على الجدول."}
            return {"status": "success", "data": data, "type": "image", "message": "تم سحب المواد كمسودة. يرجى تفعيل وضع التعديل لترتيبها."}
            
        # صيغة غير مدعومة
        return {"status": "error", "message": "صيغة غير مدعومة. ارفع PDF أو صورة."}
        
    except Exception as e:
        return {"status": "error", "message": f"حدث خطأ في السيرفر: {str(e)}"}

# ==========================================
# 4. فحص حالة السيرفر
# ==========================================
@app.get("/")
def home(): 
    return {"status": "online", "message": "EV Schedule Parser is running!"}
