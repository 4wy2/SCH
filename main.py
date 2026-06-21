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

# الحد الأقصى لحجم الملف (10 ميقابايت) لحماية ذاكرة السيرفر المجاني
MAX_FILE_SIZE = 10 * 1024 * 1024

# تجهيز التعابير النمطية مرة وحدة (أسرع من إعادة بنائها كل صف)
COURSE_PATTERN = re.compile(r'[A-Za-z]{2,4}\s?\d{3}')
SLOT_PATTERN = re.compile(r'\b(44|47|51|52|54|57|63|80|86)\b')


def parse_rcjy_table(table, seen):
    """يحلل جدول صفحة واحدة. seen عبارة عن set مشترك لمنع التكرار عبر الصفحات."""
    results = []
    if not table:
        return results

    for row in table:
        if not row or len(row) < 12:
            continue
        row_str = str(row[0] or "")
        if "Course Code" in row_str or "Total" in row_str:
            continue

        split_cells = [str(cell).split('\n') if cell else [""] for cell in row]
        num_entries = max(len(cell) for cell in split_cells)

        for i in range(num_entries):
            course_col = split_cells[0]
            course_code = course_col[i].strip() if i < len(course_col) else course_col[-1].strip()
            if not COURSE_PATTERN.search(course_code):
                continue
            course_name_clean = course_code.replace(" ", "").upper()

            # --- استخراج القاعة (نسحب الخلية كاملة ونوصل أي كسر سطر) ---
            room = "TBA"
            room_idx = 13 if len(row) > 13 else (12 if len(row) > 12 else -1)
            if room_idx != -1:
                raw_room = str(row[room_idx] or "").strip()
                cleaned = re.sub(r'\s+', ' ', raw_room.replace('\n', ' ')).strip()
                room = cleaned if cleaned else "TBA"
            # ----------------------------------------------------------

            for day_idx in range(7, 12):
                if day_idx >= len(split_cells):
                    break
                day_col = split_cells[day_idx]
                day_content = day_col[i] if i < len(day_col) else day_col[-1]

                if day_content:
                    for s in SLOT_PATTERN.findall(day_content):
                        key = (day_idx - 7, s, course_name_clean)
                        if key in seen:          # منع المادة المكررة بنفس اليوم والوقت
                            continue
                        seen.add(key)
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

        # 1) حماية الذاكرة من الملفات الضخمة
        if len(content) > MAX_FILE_SIZE:
            return {"status": "error",
                    "message": "حجم الملف كبير جداً (الحد 10 ميقا). الرجاء رفع ملف الجدول فقط."}

        # 2) قبول مرن للـ PDF: النوع أو الامتداد أو بصمة الملف %PDF-
        filename = (file.filename or "").lower()
        is_pdf = (
            file.content_type == "application/pdf"
            or filename.endswith(".pdf")
            or content[:5] == b"%PDF-"
        )
        if not is_pdf:
            return {"status": "error",
                    "message": "عذراً، النظام يقبل ملفات PDF فقط لضمان الدقة 100%."}

        # 3) نلف على كل صفحات الملف (مو صفحة وحدة) ونمنع التكرار
        seen = set()
        all_results = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                table = page.extract_table(
                    {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
                )
                all_results.extend(parse_rcjy_table(table, seen))

        if not all_results:
            return {"status": "error",
                    "message": "لم يتم العثور على مواد. تأكد من أن الملف هو جدول الإيدوقيت الأصلي."}

        return {"status": "success", "data": all_results, "type": "pdf"}

    except Exception as e:
        return {"status": "error", "message": f"حدث خطأ أثناء المعالجة: {str(e)}"}


@app.get("/")
def home():
    return {"status": "online", "message": "EV Fast PDF Parser is running!"}


# نقطة بسيطة تنفع لخدمات الـ uptime (تبقي السيرفر صاحي)
@app.get("/ping")
def ping():
    return {"ok": True}
