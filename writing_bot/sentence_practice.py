# -*- coding: utf-8 -*-
"""
Gap tuzish mashqlari — CEFR darajalari (B1, B1+, B2, B2+, C1) bo'yicha
Simple / Compound / Complex / Compound-Complex gaplarni va ularga mos
bog'lovchilarni o'rgatish va mashq qildirish moduli.
"""
import asyncio
import json
import re

from evaluator import LLM_PROVIDER, _get_gemini_client, _get_anthropic_client, GEMINI_MODEL, CLAUDE_MODEL

LEVELS = ["B1", "B1+", "B2", "B2+", "C1"]

SENTENCE_TYPES = {
    "simple": {"title": "Simple Sentence (Sodda gap)"},
    "compound": {"title": "Compound Sentence (Qo'shma gap)"},
    "complex": {"title": "Complex Sentence (Ergashgan qo'shma gap)"},
    "compound_complex": {"title": "Compound-Complex Sentence (Aralash qo'shma gap)"},
}

# Har bir daraja uchun tavsiya etiladigan bog'lovchilar (Compound/Complex/Compound-Complex uchun)
CONNECTORS_BY_LEVEL = {
    "B1": {
        "coordinating": ["and", "but", "or", "so"],
        "subordinating": ["because", "when", "if"],
    },
    "B1+": {
        "coordinating": ["and", "but", "or", "so", "yet"],
        "subordinating": ["although", "while", "since", "before", "after", "as soon as"],
    },
    "B2": {
        "coordinating": ["and", "but", "so", "yet", "for"],
        "subordinating": ["however*", "therefore*", "whereas", "unless", "provided that"],
    },
    "B2+": {
        "coordinating": ["and", "but", "so", "nor"],
        "subordinating": ["even though", "despite the fact that", "in case", "as long as"],
    },
    "C1": {
        "coordinating": ["and", "but", "so"],
        "subordinating": ["notwithstanding", "albeit", "insofar as", "on the grounds that", "not only... but also"],
    },
}
# * — herchunki "however"/"therefore" texnik jihatdan bog'lovchi zarf (conjunctive adverb),
# lekin B2 darajasida ular Compound gaplarda nuqtali vergul bilan ishlatilishi o'rgatiladi.

STATIC_THEORY = {
    "simple": """<b>Simple Sentence (Sodda gap)</b>

Bitta ega va bitta kesim (bitta mustaqil fikr) bo'lgan gap.
Misol: <i>"The weather is nice today."</i>

Sodda gap qisqa bo'lishi shart emas — unda bir nechta ega yoki kesim
bo'lishi mumkin (masalan "Tom and Jerry play"), lekin faqat BITTA mustaqil
fikr ifodalanadi, bog'lovchi orqali ikkinchi fikr qo'shilmaydi.""",

    "compound": """<b>Compound Sentence (Qo'shma gap)</b>

Ikki (yoki undan ko'p) MUSTAQIL gap, koordinatsion bog'lovchi (FANBOYS: for,
and, nor, but, or, yet, so) yoki nuqtali vergul (;) orqali birlashtiriladi.
Har ikkala qism o'z-o'zicha to'liq gap bo'lishi kerak.

Misol: <i>"I wanted to go for a walk, but it started raining."</i>

Bog'lovchidan oldin odatda VERGUL qo'yiladi.""",

    "complex": """<b>Complex Sentence (Ergashgan qo'shma gap)</b>

Bitta MUSTAQIL gap + bitta yoki bir nechta QARAM (ergash) gap, subordinatsion
bog'lovchi (because, although, when, if, since, while va h.k.) yoki nisbiy
olmosh (who, which, that) orqali bog'lanadi.

Misol: <i>"Although it was raining, we decided to go for a walk."</i>

Agar ergash gap boshda kelsa — vergul qo'yiladi. Agar oxirida kelsa — odatda
vergul kerak emas: <i>"We decided to go for a walk although it was raining."</i>""",

    "compound_complex": """<b>Compound-Complex Sentence (Aralash qo'shma gap)</b>

Kamida IKKITA mustaqil gap + kamida BITTA qaram (ergash) gapdan iborat.
Bu eng murakkab gap turi, odatda B2+/C1 darajasida ishlatiladi.

Misol: <i>"Although it was raining, we decided to go for a walk, and we
ended up having a great time."</i>

Bu yerda: "Although it was raining" — ergash gap, "we decided to go for a
walk" va "we ended up having a great time" — ikkita mustaqil gap ("and"
bilan bog'langan).""",
}


def connectors_line(level: str) -> str:
    c = CONNECTORS_BY_LEVEL[level]
    return (
        f"Shu daraja ({level}) uchun tavsiya etiladigan bog'lovchilar:\n"
        f"• Koordinatsion (compound uchun): {', '.join(c['coordinating'])}\n"
        f"• Subordinatsion (complex uchun): {', '.join(c['subordinating'])}"
    )


def _build_exercise_instruction(level: str, sentence_type: str) -> str:
    stype_title = SENTENCE_TYPES[sentence_type]["title"]
    connectors = connectors_line(level)

    if sentence_type == "simple":
        task_desc = f"Nomzoddan bitta original SIMPLE (sodda) gap yozishni so'rang, {level} darajasiga mos so'z boyligi bilan."
    elif sentence_type == "compound":
        task_desc = f"""Ikkita oddiy (simple) gapni bering (masalan "She was tired." va "She kept working.")
va nomzoddan ularni bitta COMPOUND gapga birlashtirishni so'rang, mos koordinatsion
bog'lovchi ishlatib ({level} darajasiga mos)."""
    elif sentence_type == "complex":
        task_desc = f"""Ikkita oddiy (simple) gapni bering va nomzoddan ularni bitta COMPLEX gapga
birlashtirishni so'rang, mos subordinatsion bog'lovchi ishlatib ({level} darajasiga mos)."""
    else:
        task_desc = f"""Nomzoddan bitta original COMPOUND-COMPLEX gap yozishni so'rang — kamida
2 ta mustaqil gap va 1 ta ergash gapdan iborat bo'lishi kerak ({level} darajasiga mos)."""

    return f"""Siz CEFR grammatika o'qituvchisisiz. "{stype_title}" mashqi uchun,
{level} darajasiga mos, original va qisqa vazifa yarating.

{task_desc}

{connectors}

Faqat vazifa matnini yozing (aniq va qisqa, 1-3 gap), boshqa hech qanday
izoh, sarlavha yoki "Namuna:" kabi so'z qo'shmang. Har safar boshqa mavzu
tanlang (ish, sayohat, ta'lim, oila, sport va h.k. orasidan)."""


EXERCISE_SYSTEM = """Siz tajribali CEFR grammatika o'qituvchisisiz. Original,
qisqa va aniq gap-tuzish mashqlari yaratasiz. Har safar boshqacha mavzu
tanlang, takrorlamang.

MUHIM: Bu — INGLIZ TILI grammatika mashqi. Berilgan gaplar (nomzod
birlashtirishi yoki qayta yozishi kerak bo'lgan gaplar) albatta INGLIZ
TILIDA bo'lishi kerak. Faqat vazifaning o'zini tushuntiruvchi qisqa
ko'rsatma o'zbek tilida bo'lishi mumkin."""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def _call_gemini_plain(instruction: str, system: str, max_tokens: int = 700, json_mode: bool = False) -> str:
    from google.genai import types

    client = _get_gemini_client()
    config_kwargs = dict(
        system_instruction=system,
        temperature=0.75,
        max_output_tokens=max_tokens,
    )
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=instruction,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text


async def _generate_gemini(instruction: str, system: str, max_tokens: int = 700, json_mode: bool = False) -> str:
    return await asyncio.to_thread(_call_gemini_plain, instruction, system, max_tokens, json_mode)


async def _generate_anthropic(instruction: str, system: str, max_tokens: int = 700) -> str:
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": instruction}],
    )
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


async def generate_sentence_exercise(level: str, sentence_type: str) -> str:
    """Berilgan daraja va gap turi uchun qisqa mashq vazifasini generatsiya qiladi."""
    instruction = _build_exercise_instruction(level, sentence_type)
    if LLM_PROVIDER == "anthropic":
        text = await _generate_anthropic(instruction, EXERCISE_SYSTEM)
    else:
        text = await _generate_gemini(instruction, EXERCISE_SYSTEM)
    return text.strip()


EVAL_SYSTEM = """Siz CEFR grammatika o'qituvchisisiz. Nomzodning gap tuzish
mashqiga yozgan javobini tekshirasiz: gap turi to'g'ri tuzilganmi (Simple/
Compound/Complex/Compound-Complex), bog'lovchi to'g'ri va darajaga mos
ishlatilganmi, grammatik xatolar bormi. Xatoni ANIQ va TUSHUNARLI tarzda
tushuntiring (masalan: "Bu gapda faqat bitta mustaqil qism bor, shuning
uchun bu Compound emas, Simple gap" yoki "because" o'rniga "although"
ishlatilishi kerak edi, chunki gaplar orasida qarama-qarshilik bor").

Javobingizni FAQAT quyidagi JSON formatida bering:
{
  "is_correct_type": <true/false — javob so'ralgan gap turiga mos keladimi>,
  "detected_type": "<javobda haqiqatda qanday gap turi ishlatilgani: Simple/Compound/Complex/Compound-Complex>",
  "connectors_used": ["<ishlatilgan bog'lovchilar ro'yxati>"],
  "connector_feedback": "<bog'lovchi to'g'ri/darajaga mosligi haqida qisqa izoh>",
  "grammar_errors": ["<aniq xato 1 va nima uchun xato ekanligi>", "<xato 2>"],
  "corrected_version": "<nomzod gapining to'g'irlangan/yaxshilangan versiyasi>",
  "score": <1 dan 5 gacha butun son>,
  "comment": "<2-3 gapdan iborat konstruktiv umumiy izoh, o'zbek tilida>"
}"""


def _build_eval_instruction(level: str, sentence_type: str, exercise: str, user_text: str) -> str:
    stype_title = SENTENCE_TYPES[sentence_type]["title"]
    connectors = connectors_line(level)
    return f"""Mashq turi: {stype_title}
Maqsad daraja: {level}
{connectors}

VAZIFA (nomzodga berilgan):
{exercise}

NOMZODNING JAVOBI:
{user_text}

Yuqoridagi javobni tekshiring: gap turi to'g'rimi, bog'lovchi to'g'ri va
darajaga mosmi, grammatik xatolar bormi. Faqat JSON qaytaring."""


async def evaluate_sentence_response(level: str, sentence_type: str, exercise: str, user_text: str) -> dict:
    instruction = _build_eval_instruction(level, sentence_type, exercise, user_text)
    if LLM_PROVIDER == "anthropic":
        client = _get_anthropic_client()
        response = await client.messages.create(
            model=CLAUDE_MODEL, max_tokens=900, system=EVAL_SYSTEM,
            messages=[{"role": "user", "content": instruction}],
        )
        raw = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    else:
        raw = await _generate_gemini(instruction, EVAL_SYSTEM, max_tokens=1300, json_mode=True)

    data = _extract_json(raw)
    score = data.get("score", 0)
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0
    data["score"] = max(1, min(5, score))
    return data
