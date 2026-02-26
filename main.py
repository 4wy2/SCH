from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import io
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# الفترات الرسمية في الهيئة الملكية [cite: 10]
VALID_SLOTS = ["44", "47", "51", "52", "54", "57", "63", "80", "86"]

def parse_rcjy_table(table):
    results = []
    if not table:
        return results

    for row in table:
        # تنظيف الصف وتجنب العناوين 
        if not row or "Course Code" in str(row[0]) or "Total" in str(row[0]):
            continue

        # معالجة الخلايا المتداخلة (مثل EE 204 و EE 206) 
        # نقوم بتقسيم كل خلية بناءً على السطر الجديد
        split_cells = [str(cell).split('\n') if cell else [""] for cell in row]
        
        # معرفة عدد المواد الموجودة في هذا الصف (عادة 1 أو 2)
        num_entries = max(len(cell) for cell in split_cells)

        for i in range(num_entries):
            # استخراج بيانات المادة الفرعية
            course_code = split_cells[0][i].strip() if i < len(split_cells[0]) else split_cells[0][-1].strip()
            room = split_cells[13][i].strip() if i < len(split_cells[13]) else split_cells[13][-1].strip()

            if not course_code or len(course_code) < 4:
                continue

            # فحص الأعمدة من 7 إلى 11 (Sun to Thu) 
            for day_idx in range(7, 12):
                day_content = split_cells[day_idx][i] if i < len(split_cells[day_idx]) else split_cells[day_idx][-1]
                
                # البحث عن أرقام الفترات (مثل 63,51,52) 
                if day_content:
                    slots = re.findall(r'\b(44|47|51|52|54|57|63|80|86)\b', day_content)
                    for s in slots:
                        results.append({
                            "day": day_idx - 7, # تحويل من (7-11) إلى (0-4)
                            "slotId": s,
                            "name": course_code.replace(" ", ""),
                            "room": room,
                            "color": {"bg": "#eff6ff", "text": "#1e40af"} # ألوان افتراضية
                        })
    return results

@app.post("/upload-schedule/")
async def upload_schedule(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                # استخراج الجدول بإعدادات دقيقة لخطوط الهيئة الملكية
                table = pdf.pages[0].extract_table({
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines"
                })
                data = parse_rcjy_table(table)
                return {"status": "success", "data": data}
        return {"status": "error", "message": "يرجى رفع ملف PDF"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def home(): return {"status": "online"}
