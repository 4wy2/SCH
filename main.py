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

            # --- 🪄 التعديل الجذري للقاعات ---
            room = "TBA"
            room_idx = 13 if len(row) > 13 else (12 if len(row) > 12 else -1)
            
            if room_idx != -1:
                # سحب الخلية بالكامل كقطعة نصية واحدة
                raw_room = str(row[room_idx] or "").strip()
                
                # إزالة أي كسر للسطر (\n) ناتج عن ضيق مربع الـ PDF
                # هذا يضمن أن (ACXG40,ACXG \n 66) ترجع متصلة تماماً
                room = raw_room.replace('\n', ' ')
                
                # تنظيف المسافات المزدوجة إن وجدت
                room = re.sub(r'\s+', ' ', room).strip()
            # ---------------------------------

            for day_idx in range(7, 12):
                if day_idx >= len(split_cells): break
                day_col = split_cells[day_idx]
                day_content = day_col[i] if i < len(day_col) else day_col[-1]
                
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

@app.post("/upload-schedule/")
async def upload_schedule(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                table = pdf.pages[0].extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
                data = parse_rcjy_table(table)
                if not data: return {"status": "error", "message": "لم يتم العثور على مواد. تأكد من أن الملف هو جدول الإيدوقيت الأصلي."}
                return {"status": "success", "data": data, "type": "pdf"}
        
        return {"status": "error", "message": "عذراً، النظام يقبل ملفات PDF فقط لضمان الدقة 100%."}
    except Exception as e:
        return {"status": "error", "message": f"حدث خطأ: {str(e)}"}

@app.get("/")
def home(): return {"status": "online", "message": "EV Fast PDF Parser is running!"}
