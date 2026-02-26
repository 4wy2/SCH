from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import pytesseract
from PIL import Image
import io
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_rcjy_table(table):
    results = []
    if not table: return results
    for row in table:
        if not row or len(row) < 12: continue
        row_str = str(row[0] or "")
        if "Course Code" in row_str or "Total" in row_str: continue

        split_cells = [str(cell).split('\n') if cell else [""] for cell in row]
        num_entries = max(len(cell) for cell in split_cells)

        for i in range(num_entries):
            course_col = split_cells[0]
            course_code = course_col[i].strip() if i < len(course_col) else course_col[-1].strip()
            if not re.search(r'[A-Za-z]{2,4}\s?\d{3}', course_code): continue
            course_name_clean = course_code.replace(" ", "").upper()

            room = "TBA"
            if len(split_cells) > 13:
                room_col = split_cells[13]
                room = room_col[i].strip() if i < len(room_col) else room_col[-1].strip()
            elif len(split_cells) > 12:
                room_col = split_cells[12]
                room = room_col[i].strip() if i < len(room_col) else room_col[-1].strip()

            for day_idx in range(7, 12):
                if day_idx >= len(split_cells): break
                day_col = split_cells[day_idx]
                day_content = day_col[i] if i < len(day_col) else day_col[-1]
                
                if day_content:
                    slots = re.findall(r'\b(44|47|51|52|54|57|63|80|86)\b', day_content)
                    for s in slots:
                        results.append({"day": day_idx - 7, "slotId": s, "name": course_name_clean, "room": room})
    return results

def parse_image(image_bytes):
    try:
        # إزالة الفلاتر لكي لا تتشوه ألوان الجدول الفاتحة
        img = Image.open(io.BytesIO(image_bytes))
        
        # وضع PSM 11 يساعد في قراءة الجداول المبعثرة بشكل أفضل
        text = pytesseract.image_to_string(img, config='--psm 11')
        
        courses_found = re.findall(r'[A-Za-z]{2,4}\s?\d{3}', text)
        unique_courses = list(set([c.replace(" ", "").upper() for c in courses_found]))
        
        if not unique_courses:
            # نرجع النص الذي استطاع قراءته لنرى أين الخلل
            return [], text 
            
        results = []
        default_slots = ["54", "86", "44", "80", "57", "47", "63", "52", "51"]
        for idx, course in enumerate(unique_courses):
            slot = default_slots[idx % len(default_slots)]
            results.append({"day": 0, "slotId": slot, "name": course, "room": "مسودة-عدل"})
            results.append({"day": 2, "slotId": slot, "name": course, "room": "مسودة-عدل"})
        return results, text
        
    except Exception as e:
        # نرفع الخطأ لكي يظهر في واجهة الموقع!
        raise Exception(f"Tesseract Error: {str(e)}")

@app.post("/upload-schedule/")
async def upload_schedule(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                table = pdf.pages[0].extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
                data = parse_rcjy_table(table)
                if not data: return {"status": "error", "message": "لم يتم العثور على مواد بالـ PDF."}
                return {"status": "success", "data": data, "type": "pdf"}
                
        elif file.content_type.startswith("image/"):
            try:
                data_result = parse_image(content)
                data = data_result[0]
                raw_text = data_result[1]
                
                if not data: 
                    # سيعرض لك ماذا قرأ السيرفر بالضبط من الصورة!
                    snippet = raw_text[:100].replace('\n', ' ')
                    return {"status": "error", "message": f"السيرفر قرأ هذا النص فقط: ({snippet}) ولم يجد مواد."}
                    
                return {"status": "success", "data": data, "type": "image", "message": "تم سحب المواد كمسودة. يرجى תفعيل وضع التعديل."}
            except Exception as img_e:
                # إذا لم يكن Tesseract مثبتاً ستظهر هذه الرسالة
                return {"status": "error", "message": f"السيرفر يفتقد محرك الصور: {str(img_e)}"}
                
        return {"status": "error", "message": "صيغة غير مدعومة. ارفع PDF أو صورة."}
    except Exception as e:
        return {"status": "error", "message": f"خطأ عام: {str(e)}"}

@app.get("/")
def home(): return {"status": "online"}
