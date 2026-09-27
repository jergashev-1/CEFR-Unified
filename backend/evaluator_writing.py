# -*- coding: utf-8 -*-
"""
LLM orqali yozma javobni CEFR mezonlari asosida baholash.
(Foydalanuvchining ishlab turgan Writing botidan olingan, o'zgarishsiz.)
Standart: Google Gemini (bepul). Ixtiyoriy: Anthropic Claude.
"""
import asyncio
import json
import os
import re

from rubrics import TASKS

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

_gemini_client = None
_anthropic_client = None


SYSTEM_PROMPT = """Siz tajribali CEFR (Multilevel Writing) baholovchi ekspertsiz.
Sizga vazifa tavsifi, baholash shkalasi va nomzodning yozma javobi beriladi.
Vazifangiz — javobni berilgan holistik shkala asosida xolisona, izchil va
adolatli baholash, HAMDA nomzod matnidagi aniq xatolarni turkumlab ko'rsatish.

Qoidalar:
- Faqat berilgan shkaladagi butun ball (0 dan max ballgacha) qo'ying.
- Baho vazifa bajarilishi, tuzilma/izchillik (coherence/cohesion), grammatika
  diapazoni va aniqligi, leksika diapazoni va aniqligi, hamda janr/registrga
  mosligi asosida qo'yiladi.
- So'zlar soni tavsiya etilgan oraliqdan sezilarli farq qilsa, buni izohda
  qayd eting, lekin faqat shu sabab bilan ballni haddan tashqari kamaytirmang.
- Matndagi har bir aniq xatoni "errors" ro'yxatida alohida elementga kiriting.
  Har bir xato aniq TURKUMLARDAN BIRIGA tegishli bo'lishi shart:
    "grammar"   — grammatik xato (zamon, kelishik, artikl, so'z tartibi va h.k.)
    "spelling"  — imloviy xato (noto'g'ri yozilgan so'z)
    "run_on"    — run-on gap yoki noto'g'ri tinish belgilari
    "register"  — uslub/registr xatosi
  Har bir xato uchun:
    "original"    — nomzod matnidan XATOLIK BO'LGAN ANIQ QISM
    "correction"  — to'g'irlangan varianti
    "explanation" — nima uchun xato ekanligi haqida 1 qisqa gap, o'zbek tilida
  Agar biror turkumda xato topilmasa, shu turkum uchun element qo'shmang
  (kamida 3-8 ta eng muhim xatoni ko'rsating).
- Javobingizni albatta FAQAT quyidagi JSON formatida bering, boshqa hech
  qanday matn qo'shmang:

{
  "score": <butun son>,
  "estimated_cefr_level": "<masalan A2/B1/B1+/B2/C1 va h.k.>",
  "word_count_comment": "<so'zlar soni haqida qisqa izoh>",
  "strengths": ["<kuchli tomon 1>", "<kuchli tomon 2>"],
  "improvements": ["<yaxshilash kerak bo'lgan tomon 1>", "<... 2>"],
  "errors": [
    {
      "type": "grammar|spelling|run_on|register",
      "original": "<matndan aynan olingan xato qism>",
      "correction": "<to'g'irlangan varianti>",
      "explanation": "<qisqa izoh, o'zbek tilida>"
    }
  ],
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

    decoder = json.JSONDecoder()

    # Avval to'g'ridan-to'g'ri urinamiz (eng tez yo'l, aksariyat holatda ishlaydi)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Model JSON obyektidan keyin qo'shimcha matn/JSON qo'shib yuborgan bo'lishi
    # mumkin ("Extra data" xatosi). raw_decode faqat BIRINCHI to'liq va to'g'ri
    # JSON obyektini o'qib, undan keyingi hamma narsani e'tiborsiz qoldiradi.
    start = raw.find("{")
    if start == -1:
        raise ValueError(f"Javobda JSON obyekti topilmadi: {raw[:200]!r}")

    obj, _end_index = decoder.raw_decode(raw, start)
    return obj


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY topilmadi. Render Environment Variables'ga qo'shing "
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
            max_output_tokens=3000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text


async def _evaluate_gemini(task_key: str, text: str, custom_prompt: str | None) -> dict:
    raw_text = await asyncio.to_thread(_call_gemini_sync, task_key, text, custom_prompt)
    return _extract_json(raw_text)


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY topilmadi. Render Environment Variables'ga qo'shing.")
        _anthropic_client = AsyncAnthropic(api_key=api_key)
    return _anthropic_client


async def _evaluate_anthropic(task_key: str, text: str, custom_prompt: str | None) -> dict:
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(task_key, text, custom_prompt)}],
    )
    raw_text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return _extract_json(raw_text)


async def evaluate(task_key: str, text: str, custom_prompt: str | None = None) -> dict:
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
    data["max_score"] = task["max_score"]
    data["errors"] = _sanitize_errors(data.get("errors"))

    return data


_VALID_ERROR_TYPES = {"grammar", "spelling", "run_on", "register"}


def _sanitize_errors(errors) -> list:
    if not isinstance(errors, list):
        return []
    cleaned = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        err_type = str(item.get("type", "")).strip().lower()
        if err_type not in _VALID_ERROR_TYPES:
            continue
        original = str(item.get("original", "")).strip()
        correction = str(item.get("correction", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        if not original:
            continue
        cleaned.append({
            "type": err_type,
            "original": original,
            "correction": correction,
            "explanation": explanation,
        })
    return cleaned


# ---------------------------------------------------------------------------
# Mavzu/topshiriq matnini generatsiya qilish (har safar yangi, original)
# ---------------------------------------------------------------------------

PROMPT_GEN_SYSTEM = """You are an expert item-writer for a CEFR Multilevel
Writing exam. Each time, invent an original, different situation or topic
(various domains: clubs, schools, companies, local organisations, public
places, technology, health, travel, etc.). The register should be neutral,
simple and natural. The task text itself MUST be written entirely in
ENGLISH (this is a language exam — candidates must read and respond to an
English-language prompt). Reply ONLY in the requested format, with no extra
commentary or explanation, and do not translate or add anything in any
other language."""


def _email_prompt_instruction(task_key: str, task: dict) -> str:
    role = "a FRIEND, in an informal, friendly style" if task_key == "1.1" else "a STRANGER/OFFICIAL person (e.g. an organisation manager), in a formal style"
    return f"""Follow the EXAMPLE below closely in structure and style, but
write a COMPLETELY DIFFERENT, ORIGINAL topic/situation. Write the whole
task ENTIRELY IN ENGLISH.

EXAMPLE:
---
Hello,

Our city library has introduced a new online membership system. Some of
our members have been having trouble logging in. We would like to ask
you to:
1. Describe how you registered on the new system.
2. Describe any problems you encountered.
3. Suggest how the system could be improved.

Best regards,
The City Library Team
---

Write a letter to your friend about your feelings and experience with this
system.
---

NOW, following the same pattern, write your own original English text
about a DIFFERENT organisation and DIFFERENT situation (choose from, e.g.,
a sports club, an online course, a local cafe, a mobile app, an employer,
etc. — DO NOT reuse the library/registration topic). Make sure there are
exactly 3 clear numbered points. At the end, give the candidate an
instruction that they must write a letter to {role}, and must address all
3 points. Recommended length: {task['word_range']}.

Write ONLY the final English text (the message from the organisation +
instruction), with no extra commentary, heading, or the word "EXAMPLE"."""


def _essay_prompt_instruction(task: dict) -> str:
    return f"""Follow the EXAMPLE below in style, but write a COMPLETELY
DIFFERENT, ORIGINAL topic. Write the whole task ENTIRELY IN ENGLISH.

EXAMPLE:
---
Many people can no longer imagine life without social media. Do you think
social media brings more benefit or harm to our lives? Give your opinion
and support it with examples. Write your blog post.
---

NOW, in the same style, write your own original English topic on a
DIFFERENT subject (choose from, e.g., technology, health, education,
travel, work life, the environment, society, etc. — DO NOT reuse the
social media topic). Write 2-3 sentences: a situation/question, plus an
instruction such as "give your opinion and support it with examples."
Recommended length: {task['word_range']}.

Write ONLY the final English topic text, with no extra commentary,
heading, or the word "EXAMPLE"."""


def _build_prompt_gen_instruction(task_key: str) -> str:
    task = TASKS[task_key]
    if task_key in ("1.1", "1.2"):
        body = _email_prompt_instruction(task_key, task)
    else:
        body = _essay_prompt_instruction(task)
    return f"{body}\n\nTarget level: {task['target_level']}."


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
            thinking_config=types.ThinkingConfig(thinking_budget=0),
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
    instruction = _build_prompt_gen_instruction(task_key)
    if LLM_PROVIDER == "anthropic":
        text = await _generate_anthropic_prompt(instruction)
    else:
        text = await _generate_gemini_prompt(instruction)
    return text.strip()
