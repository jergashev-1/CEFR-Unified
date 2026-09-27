# -*- coding: utf-8 -*-
"""
LLM orqali yozma javobni CEFR mezonlari asosida baholash.
Ikki provayderni qo'llab-quvvatlaydi:
  - "gemini"    -> Google Gemini API (BEPUL, kunlik kvota bilan) — STANDART
  - "anthropic" -> Claude API (pullik, lekin sifatliroq bo'lishi mumkin)

Qaysi provayder ishlatilishi .env dagi LLM_PROVIDER orqali belgilanadi.
"""
import asyncio
import json
import os
import re

from rubrics import TASKS

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

_gemini_client = None
_anthropic_client = None


SYSTEM_PROMPT = """Siz tajribali CEFR (Multilevel Writing) baholovchi ekspertsiz.
Sizga vazifa tavsifi, baholash shkalasi va nomzodning yozma javobi beriladi.
Vazifangiz — javobni berilgan holistik shkala asosida xolisona, izchil va
adolatli baholash.

Qoidalar:
- Faqat berilgan shkaladagi butun ball (0 dan max ballgacha) qo'ying.
- Baho vazifa bajarilishi, tuzilma/izchillik (coherence/cohesion), grammatika
  diapazoni va aniqligi, leksika diapazoni va aniqligi, hamda janr/registrga
  mosligi asosida qo'yiladi.
- So'zlar soni tavsiya etilgan oraliqdan sezilarli farq qilsa, buni izohda
  qayd eting, lekin faqat shu sabab bilan ballni haddan tashqari kamaytirmang.
- Javobingizni albatta FAQAT quyidagi JSON formatida bering, boshqa hech
  qanday matn qo'shmang:

{
  "score": <butun son>,
  "estimated_cefr_level": "<masalan A2/B1/B1+/B2/C1 va h.k.>",
  "word_count_comment": "<so'zlar soni haqida qisqa izoh>",
  "strengths": ["<kuchli tomon 1>", "<kuchli tomon 2>"],
  "improvements": ["<yaxshilash kerak bo'lgan tomon 1>", "<... 2>"],
  "comment": "<2-4 gapdan iborat umumiy, konstruktiv izoh, o'zbek tilida>"
}
"""


def _build_user_prompt(task_key: str, text: str, custom_prompt: str | None = None) -> str:
    task = TASKS[task_key]
    word_count = len(text.split())
    prompt_section = ""
    if custom_prompt:
        prompt_section = f"""
NOMZODGA BERILGAN ASL TOPSHIRIQ MATNI (baholashda javob shu topshiriqqa qay
darajada mos kelishini — "task achievement" — albatta hisobga oling):
---
{custom_prompt}
---
"""
    return f"""VAZIFA: {task['title']}
Maqsad daraja: {task['target_level']}
Tavsiya etilgan hajm: {task['word_range']}
Maksimal ball: {task['max_score']}

BAHOLASH MEZONI:
{task['rubric']}
{prompt_section}
NOMZODNING JAVOBI (so'zlar soni: {word_count}):
---
{text}
---

Yuqoridagi mezon asosida ushbu javobni baholang va faqat JSON qaytaring."""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Model JSON atrofiga qo'shimcha matn qo'shib yuborgan bo'lishi mumkin —
        # birinchi '{' va oxirgi '}' orasidagi qismni ajratib qayta urinib ko'ramiz.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


# ---------------------------------------------------------------------------
# GEMINI (bepul)
# ---------------------------------------------------------------------------

def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY topilmadi. .env fayliga qo'shing "
                "(https://aistudio.google.com/apikey dan bepul olinadi)."
            )
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _call_gemini_sync(task_key: str, text: str, custom_prompt: str | None) -> str:
    from google.genai import types

    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_build_user_prompt(task_key, text, custom_prompt),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=2000,
        ),
    )
    return response.text


async def _evaluate_gemini(task_key: str, text: str, custom_prompt: str | None) -> dict:
    raw_text = await asyncio.to_thread(_call_gemini_sync, task_key, text, custom_prompt)
    return _extract_json(raw_text)


# ---------------------------------------------------------------------------
# ANTHROPIC / CLAUDE (pullik)
# ---------------------------------------------------------------------------

def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY topilmadi. .env fayliga qo'shing."
            )
        _anthropic_client = AsyncAnthropic(api_key=api_key)
    return _anthropic_client


async def _evaluate_anthropic(task_key: str, text: str, custom_prompt: str | None) -> dict:
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(task_key, text, custom_prompt)}],
    )
    raw_text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return _extract_json(raw_text)


# ---------------------------------------------------------------------------
# Umumiy interfeys
# ---------------------------------------------------------------------------

async def evaluate(task_key: str, text: str, custom_prompt: str | None = None) -> dict:
    """Berilgan matnni tegishli vazifa mezoni asosida baholaydi.
    LLM_PROVIDER (.env) ga qarab Gemini (bepul) yoki Claude (pullik) ishlatiladi.
    custom_prompt berilsa (bot generatsiya qilgan mavzu matni), baholashda
    javob shu topshiriqqa mos kelishi ham hisobga olinadi.
    Xatolik (masalan model noto'g'ri formatda javob bersa yoki server band bo'lsa)
    yuzaga kelsa, buni yashirmasdan yuqoriga (bot.py'ga) uzatadi — shunda avtomatik
    va qo'lda "Qayta urinish" mexanizmi to'g'ri ishlaydi.
    """
    task = TASKS[task_key]

    if LLM_PROVIDER == "anthropic":
        data = await _evaluate_anthropic(task_key, text, custom_prompt)
    else:
        data = await _evaluate_gemini(task_key, text, custom_prompt)

    score = data.get("score", 0)
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0
    data["score"] = max(0, min(task["max_score"], score))

    return data


# ---------------------------------------------------------------------------
# Mavzu/topshiriq matnini generatsiya qilish (Aniq mavzu funksiyasi)
# ---------------------------------------------------------------------------

PROMPT_GEN_SYSTEM = """Siz CEFR Multilevel Writing imtihoni uchun topshiriq
(mavzu) tuzuvchi ekspertsiz. Har safar original, boshqa-boshqa vaziyat yoki
mavzu o'ylab toping (turli sohalar: klublar, maktablar, kompaniyalar,
mahalliy tashkilotlar, jamoat joylari, texnologiya, sog'liq, sayohat va h.k.).
Til uslubi tarafsiz (neytral), oddiy va tabiiy bo'lsin.

MUHIM: Bu — INGLIZ TILI imtihoni, shuning uchun generatsiya qilinadigan
YAKUNIY MATNNING O'ZI (xabar, ko'rsatma, mavzu) albatta FAQAT INGLIZ TILIDA
bo'lishi kerak. Faqat so'ralgan formatda javob bering, hech qanday qo'shimcha
izoh yoki tushuntirish (o'zbek yoki boshqa tilda) yozmang."""


def _email_prompt_instruction(task_key: str, task: dict) -> str:
    role = "a FRIEND, in an informal, friendly tone" if task_key == "1.1" else "an UNFAMILIAR/FORMAL person (e.g. a manager), in a formal tone"
    return f"""Following the EXAMPLE below (same structure and style), write a
COMPLETELY DIFFERENT, ORIGINAL scenario. The example is in English — your
new text must ALSO be written ENTIRELY IN ENGLISH.

EXAMPLE:
---
Hello,

Our local library has launched a new online membership system. Some of our
members have experienced difficulties logging into it. We would like to ask
you to:
1. Describe how you registered for the new system.
2. Describe any problems you encountered.
3. Suggest ways to improve the system.

Best regards,
City Library Team
---

Write a letter to your friend about your feelings and experience with this
new system.
---

NOW, following this example, write your OWN original text (in ENGLISH) about
a DIFFERENT organization and situation (e.g. a sports club, an online
course, a local cafe, a mobile app, an employer, etc. — do NOT reuse the
library/registration topic). It must include exactly 3 clear points the
candidate must respond to. At the end, instruct the candidate to write to
{role}, addressing all 3 points. Target length for the candidate's response: {task['word_range']}.

Write ONLY the final text (the organization's message + the instruction),
in ENGLISH, with no extra commentary, headings, or the word "Example:"."""


def _essay_prompt_instruction(task: dict) -> str:
    return f"""Following the EXAMPLE below, write a COMPLETELY DIFFERENT,
ORIGINAL topic. The example is in English — your new text must ALSO be
written ENTIRELY IN ENGLISH.

EXAMPLE:
---
Many people nowadays cannot imagine their lives without social media. Do you
think social media brings more benefits or more harm to our lives? Give your
opinion and support it with examples in your blog post.
---

NOW, following this example, write your OWN original topic (in ENGLISH)
about a DIFFERENT subject (technology, health, education, travel, work
life, the environment, society, etc. — do NOT reuse the social media
topic). Write 2-3 sentences: a situation/question + an instruction to give
an opinion supported with examples. Target length for the candidate's
response: {task['word_range']}.

Write ONLY the final topic text, in ENGLISH, with no extra commentary,
headings, or the word "Example:"."""


def _build_prompt_gen_instruction(task_key: str) -> str:
    task = TASKS[task_key]
    if task_key in ("1.1", "1.2"):
        body = _email_prompt_instruction(task_key, task)
    else:
        body = _essay_prompt_instruction(task)
    return f"{body}\n\nMaqsad daraja: {task['target_level']}."


def _call_gemini_plain_sync(instruction: str) -> str:
    from google.genai import types

    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=instruction,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT_GEN_SYSTEM,
            temperature=0.8,
            max_output_tokens=2000,
        ),
    )
    return response.text


async def _generate_gemini_prompt(instruction: str) -> str:
    return await asyncio.to_thread(_call_gemini_plain_sync, instruction)


async def _generate_anthropic_prompt(instruction: str) -> str:
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        system=PROMPT_GEN_SYSTEM,
        messages=[{"role": "user", "content": instruction}],
    )
    return "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )


async def generate_task_prompt(task_key: str) -> str:
    """Berilgan vazifa uchun original mavzu/topshiriq matnini generatsiya qiladi."""
    instruction = _build_prompt_gen_instruction(task_key)
    if LLM_PROVIDER == "anthropic":
        text = await _generate_anthropic_prompt(instruction)
    else:
        text = await _generate_gemini_prompt(instruction)
    return text.strip()
