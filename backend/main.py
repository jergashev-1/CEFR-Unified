"""
CEFR Multilevel Test - Backend API
Speaking va Writing baholash uchun asosiy server.

Ishga tushirish (lokal test uchun):
    uvicorn main:app --reload --port 8000

Deploy qilinganda (Render.com) start command:
    uvicorn main:app --host 0.0.0.0 --port $PORT

MUHIM: Render'ga quyidagi Environment Variables kerak:
    GEMINI_API_KEY   - Writing baholash uchun (https://aistudio.google.com/apikey)
    GROQ_API_KEY     - Speaking baholash + Whisper uchun (https://console.groq.com/keys)
"""

import os
import uuid
import shutil
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from rubrics import TASKS as WRITING_TASKS, get_standard_score
from evaluator_writing import evaluate as evaluate_writing, generate_task_prompt

from rubric import PART_LABELS, get_rubric, get_max_score
from transcriber import transcribe_audio
from evaluator_speaking import evaluate_transcript
from vision import extract_question_from_image
from question_bank import get_random_question
from picture_bank import get_random_picture_pair
from shadowing_bank import get_random_sentence
from shadowing_evaluator import compare_texts, evaluate_shadowing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CEFR Test API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
async def root():
    return {"message": "CEFR Test API ishlayapti ✅"}


# ---------------------------------------------------------------------------
# WRITING: bo'limlar ro'yxati (statik ma'lumot, prompt bundan tashqari)
# ---------------------------------------------------------------------------
@app.get("/api/writing-tasks-info")
async def writing_tasks_info():
    """Frontend uchun: har bir task haqida statik ma'lumot (prompt'siz)."""
    return {
        key: {
            "title": t["title"],
            "target_level": t["target_level"],
            "word_range": t["word_range"],
            "max_score": t["max_score"],
        }
        for key, t in WRITING_TASKS.items()
    }


# ---------------------------------------------------------------------------
# WRITING: yangi, original mavzu generatsiya qilish (botdagidek, har safar yangi)
# ---------------------------------------------------------------------------
@app.get("/api/writing-task/{task_key}")
async def get_writing_task(task_key: str):
    if task_key not in WRITING_TASKS:
        raise HTTPException(status_code=400, detail="Noto'g'ri task_key")

    try:
        prompt_text = await generate_task_prompt(task_key)
    except Exception as e:
        logger.exception("Writing task generatsiyasida xatolik")
        raise HTTPException(status_code=502, detail=f"Mavzu generatsiya qilishda xatolik: {e}")

    task = WRITING_TASKS[task_key]
    return {
        "task_key": task_key,
        "title": task["title"],
        "target_level": task["target_level"],
        "word_range": task["word_range"],
        "max_score": task["max_score"],
        "prompt": prompt_text,
    }


# ---------------------------------------------------------------------------
# WRITING: javobni baholash (matn HAM, fayl HAM qabul qilinadi)
# ---------------------------------------------------------------------------
@app.post("/api/submit-writing")
async def submit_writing(
    task_id: str = Form(...),
    user_id: str = Form(...),
    prompt_text: str = Form(""),          # foydalanuvchiga ko'rsatilgan aynan shu topshiriq matni
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    if task_id not in WRITING_TASKS:
        raise HTTPException(status_code=400, detail="Noto'g'ri task_id")

    final_text = text or ""

    if file is not None:
        ext = os.path.splitext(file.filename)[1].lower()
        filename = f"{user_id}_{task_id}_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
        final_text = extract_text_from_file(filepath, ext)

    if not final_text.strip():
        raise HTTPException(status_code=400, detail="Matn yoki fayl bo'sh")

    try:
        result = await evaluate_writing(task_id, final_text, custom_prompt=prompt_text or None)
    except Exception as e:
        logger.exception("Writing baholashda xatolik")
        raise HTTPException(status_code=502, detail=f"Baholashda xatolik: {e}")

    result["word_count"] = len(final_text.split())
    result["task_title"] = WRITING_TASKS[task_id]["title"]
    return result


# ---------------------------------------------------------------------------
# SPEAKING: qismlar ro'yxati
# ---------------------------------------------------------------------------
@app.get("/api/speaking-parts")
async def speaking_parts():
    return {
        key: {"label": label, "max_score": get_max_score(key)}
        for key, label in PART_LABELS.items()
    }


# ---------------------------------------------------------------------------
# SHADOWING: jumla olish
# ---------------------------------------------------------------------------
@app.get("/api/shadowing/sentence/{level}")
async def shadowing_sentence(level: str):
    return get_random_sentence(level.upper())


# ---------------------------------------------------------------------------
# SHADOWING: javobni baholash
# ---------------------------------------------------------------------------
@app.post("/api/shadowing/submit")
async def submit_shadowing(
    audio: UploadFile = File(...),
    target_text: str = Form(...),
    user_id: str = Form(...),
):
    ext = os.path.splitext(audio.filename)[1] or ".webm"
    filename = f"shadow_{user_id}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    try:
        metrics = await transcribe_audio(filepath, language="en")

        if not metrics.text.strip():
            raise HTTPException(status_code=400, detail="Audio bo'sh yoki tushunarsiz, qayta urinib ko'ring")

        comparison = compare_texts(target_text, metrics.text)
        feedback = await evaluate_shadowing(
            target_text, metrics.text, comparison["accuracy_percent"], metrics.summary_uz()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Shadowing baholashda xatolik")
        raise HTTPException(status_code=502, detail=f"Baholashda xatolik: {e}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass

    return {
        "transcript": metrics.text,
        "accuracy_percent": comparison["accuracy_percent"],
        "words": comparison["words"],
        "audio_metrics_summary": metrics.summary_uz(),
        "feedback": feedback,
    }


# ---------------------------------------------------------------------------
# SPEAKING: tasodifiy savol olish (Part 1.1/1.2/2/3)
# ---------------------------------------------------------------------------
@app.get("/api/random-question/{part}")
async def random_question(part: str):
    if part not in PART_LABELS:
        raise HTTPException(status_code=400, detail="Noto'g'ri part")

    if part == "1.2":
        try:
            pair = await get_random_picture_pair()
        except Exception as e:
            logger.exception("Tasodifiy surat juftini olishda xatolik")
            raise HTTPException(status_code=502, detail=f"Suratlarni olishda xatolik: {e}")

        questions_text = "\n".join(pair["questions"])
        return {
            "type": "picture_pair",
            "image1_url": pair["image1_url"],
            "image2_url": pair["image2_url"],
            "questions_text": questions_text,
        }

    question = get_random_question(part)
    return {"type": "text", "question_text": question}


# ---------------------------------------------------------------------------
# SPEAKING: savolni rasm (screenshot) orqali o'qish
# ---------------------------------------------------------------------------
@app.post("/api/extract-question-image")
async def extract_question_image(image: UploadFile = File(...)):
    ext = os.path.splitext(image.filename)[1] or ".jpg"
    filename = f"question_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(image.file, f)

    try:
        extracted = await extract_question_from_image(filepath)
    except Exception as e:
        logger.exception("Rasmdan savol o'qishda xatolik")
        raise HTTPException(status_code=502, detail=f"Rasmni o'qishda xatolik: {e}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass

    return {"extracted_text": extracted}


# ---------------------------------------------------------------------------
# SPEAKING: audio yuklash va baholash (jonli yozilgan HAM, fayl HAM)
# ---------------------------------------------------------------------------
@app.post("/api/submit-speaking")
async def submit_speaking(
    audio: UploadFile = File(...),
    user_id: str = Form(...),
    part: str = Form("1.1"),          # "1.1" | "1.2" | "2" | "3"
    question_text: str = Form(""),    # nomzodga berilgan savol (ixtiyoriy, mavjud bo'lsa)
):
    if part not in PART_LABELS:
        raise HTTPException(status_code=400, detail="Noto'g'ri part")

    ext = os.path.splitext(audio.filename)[1] or ".ogg"
    filename = f"{user_id}_{part}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    try:
        metrics = await transcribe_audio(filepath, language="en")

        if not metrics.text.strip():
            raise HTTPException(status_code=400, detail="Audio bo'sh yoki tushunarsiz, iltimos qayta urinib ko'ring")

        rubric_text = get_rubric(part)
        report = await evaluate_transcript(
            metrics.text,
            rubric_text,
            questions=question_text,
            audio_metrics_summary=metrics.summary_uz(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Speaking baholashda xatolik")
        raise HTTPException(status_code=502, detail=f"Baholashda xatolik: {e}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass

    return {
        "status": "ok",
        "part": part,
        "part_label": PART_LABELS[part],
        "transcript": metrics.text,
        "audio_metrics_summary": metrics.summary_uz(),
        "report": report,
    }


# ---------------------------------------------------------------------------
# Yordamchi funksiya: fayldan matn chiqarish (docx / pdf / txt)
# ---------------------------------------------------------------------------
def extract_text_from_file(filepath: str, ext: str) -> str:
    if ext == ".txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == ".docx":
        import docx
        doc = docx.Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        raise HTTPException(status_code=400, detail=f"Qo'llab-quvvatlanmaydigan fayl turi: {ext}")
