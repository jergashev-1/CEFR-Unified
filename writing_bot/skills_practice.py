# -*- coding: utf-8 -*-
"""
Yozish mashqlari — alohida ko'nikmalarni (Introduction, Body, Conclusion,
Conciseness, Paraphrase, Complex sentences) CEFR darajasiga mos o'rgatish
va mashq qildirish moduli.
"""
import asyncio
import json
import re

from evaluator import LLM_PROVIDER, _get_gemini_client, _get_anthropic_client, GEMINI_MODEL, CLAUDE_MODEL

LEVELS = ["B1", "B2", "C1"]

SKILLS = {
    "intro": {"title": "✍️ Introduction (Kirish qismi)", "short": "Introduction"},
    "body1": {"title": "📄 Main Body 1 (Asosiy qism 1)", "short": "Main Body 1"},
    "body2": {"title": "📄 Main Body 2 (Asosiy qism 2)", "short": "Main Body 2"},
    "conclusion": {"title": "🏁 Conclusion (Xulosa)", "short": "Conclusion"},
    "conciseness": {"title": "✂️ Conciseness (Qisqa-lo'nda yozish)", "short": "Conciseness"},
    "paraphrase": {"title": "🔄 Paraphrase (Qayta ifodalash)", "short": "Paraphrase"},
    "complex_sentence": {"title": "🧩 Complex Sentences (Murakkab gaplar)", "short": "Complex sentence"},
}

STATIC_THEORY = {
    "intro": """<b>Introduction (Kirish qismi) qanday yoziladi?</b>

Yaxshi kirish qismi 3 narsani bajaradi:
1. <b>Hook</b> — o'quvchi e'tiborini tortadigan bir gap (savol, qiziq fakt, umumiy holat).
2. Mavzuni aniq bildirish — nima haqida yozayotganingizni tushuntiring.
3. Asosiy fikringizni (thesis) yoki keyingi qismda nima muhokama qilinishini ko'rsating.

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Oddiy, to'g'ridan-to'g'ri kirish. 2-3 gap yetarli.
• <b>B2</b>: Biroz murakkabroq tuzilma, aniqroq thesis statement, bog'lovchilar (however, in recent years) ishlatiladi.
• <b>C1</b>: Nozik hook (statistika, rhetorical savol), aniq va nuanced thesis, akademik ohang.""",

    "body1": """<b>Main Body 1 (Birinchi asosiy paragraf) qanday yoziladi?</b>

Har bir asosiy paragraf odatda shunday tuzilgan:
1. <b>Topic sentence</b> — paragrafning asosiy fikri (1-gap).
2. <b>Support/Explanation</b> — fikrni tushuntirish yoki asoslash.
3. <b>Example</b> — aniq misol yoki dalil.
4. (Ixtiyoriy) Xulosa yoki keyingi paragrafga o'tish gapi.

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Oddiy topic sentence + 1 ta oddiy misol.
• <b>B2</b>: Aniqroq dalillar, 2 ta bog'lovchi vosita (for example, this shows that).
• <b>C1</b>: Chuqurroq tahlil, qarama-qarshi fikrni ham qisqa tan olish (counter-argument), nozik bog'lanish.""",

    "body2": """<b>Main Body 2 (Ikkinchi asosiy paragraf) qanday yoziladi?</b>

Ikkinchi paragraf birinchisidan <b>farqli, lekin bog'liq</b> fikrni ochib berishi kerak:
1. Yangi topic sentence (birinchisini takrorlamang).
2. Uni tushuntiring va misol bilan qo'llab-quvvatlang.
3. Birinchi paragraf bilan mantiqiy bog'lanish (masalan "In addition", "On the other hand").

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Yangi, sodda fikr, oddiy bog'lovchi (also, another reason).
• <b>B2</b>: Fikrlar orasida aniq mantiqiy ketma-ketlik, xilma-xil bog'lovchilar.
• <b>C1</b>: Qarama-qarshi yoki murakkab fikrni ishonarli tarzda rivojlantirish.""",

    "conclusion": """<b>Conclusion (Xulosa) qanday yoziladi?</b>

Yaxshi xulosa:
1. Asosiy fikrlarni <b>qisqacha</b> umumlashtiradi (takrorlamaydi, xuddi so'zma-so'z emas).
2. Kirish qismidagi thesis'ga qaytadi (boshqacha so'zlar bilan).
3. Yakuniy fikr, tavsiya yoki kelajakka oid mulohaza bilan tugaydi.

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Oddiy umumlashtirish, 1-2 gap.
• <b>B2</b>: Umumlashtirish + shaxsiy fikr yoki tavsiya.
• <b>C1</b>: Kengroq kontekstga bog'lash (jamiyat, kelajak), nozik va ishonarli yakun.""",

    "conciseness": """<b>Conciseness (Qisqa va lo'nda yozish) nima?</b>

Ortiqcha so'zlarsiz, aniq fikr bildirish. Ko'p uchraydigan xatolar:
• Ortiqcha takror: "in my opinion, I think that..." — ikkalasi ham bir xil ma'noni bildiradi.
• Bo'sh iboralar: "due to the fact that" → "because" deb qisqartiring.
• Keraksiz sifatlovchilar: "very very important" → "crucial".

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Asosiy maqsad — tushunarli va to'g'ri gaplar, uzunlik unchalik muhim emas.
• <b>B2</b>: Ortiqcha takrorlardan qochish boshlanadi.
• <b>C1</b>: Har bir so'z aniq maqsadga xizmat qiladi, iqtisodiy va ta'sirchan uslub.""",

    "paraphrase": """<b>Paraphrase (Qayta ifodalash) nima?</b>

Bir fikrni boshqa so'zlar va tuzilma bilan, ma'nosini o'zgartirmasdan qayta
ifodalash. Bu ayniqsa Task 2 (Introduction va Conclusion'da asosiy fikrni
takrorlashda) juda muhim.

Usullar:
1. Sinonimlardan foydalanish (important → crucial, significant).
2. Gap tuzilishini o'zgartirish (Active → Passive, yoki teskarisi).
3. So'z turkumini o'zgartirish (decide → decision, popular → popularity).

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Oddiy sinonimlar bilan qayta yozish.
• <b>B2</b>: Gap tuzilishini ham o'zgartirish.
• <b>C1</b>: Ma'noni saqlab, butunlay boshqa tuzilma va boy leksika bilan qayta ifodalash.""",

    "complex_sentence": """<b>Complex Sentences (Murakkab gaplar) qanday yasaladi?</b>

Murakkab gap — bosh gap + ergash gap(lar)dan iborat. Bog'lovchilar:
• Sabab: because, since, as
• Qarama-qarshilik: although, even though, while, whereas
• Shart: if, unless, provided that
• Nisbiy: who, which, that, where
• Vaqt: when, while, before, after, as soon as

Misol: "Although the weather was bad, we decided to go hiking because we
had been planning the trip for months."

<b>Daraja bo'yicha farq:</b>
• <b>B1</b>: Oddiy ergash gaplar (because, when, if).
• <b>B2</b>: Turli bog'lovchilar, ba'zan ikkita ergash gap bitta gapda.
• <b>C1</b>: Murakkab, ko'p qavatli gaplar, inversiya va nozik bog'lovchilar (whereas, provided that, not only... but also).""",
}


def _build_exercise_instruction(skill_key: str, level: str) -> str:
    skill = SKILLS[skill_key]["short"]
    base = f"""Siz CEFR Writing o'qituvchisisiz. Nomzod uchun {level} darajasiga
mos, FAQAT "{skill}" ko'nikmasini mashq qildiradigan qisqa vazifa yarating."""

    specifics = {
        "intro": f"Bir mavzu bering va nomzoddan FAQAT o'sha mavzu uchun Introduction (kirish) paragrafini ({level} darajasida, 2-4 gap) yozishni so'rang.",
        "body1": f"Bir mavzu va asosiy fikr (topic sentence g'oyasi) bering, nomzoddan o'sha fikrni rivojlantirib, bitta Main Body paragrafini ({level} darajasida, 3-5 gap) yozishni so'rang.",
        "body2": f"Bir mavzu va IKKI xil fikr yo'nalishi bering (masalan ijobiy va salbiy tomonlar), nomzoddan IKKINCHI fikr yo'nalishi bo'yicha Main Body paragrafini ({level} darajasida, 3-5 gap) yozishni so'rang.",
        "conclusion": f"Qisqacha bir mavzu va uning asosiy fikrlarini (2-3 band) bering, nomzoddan shu mavzu uchun Conclusion (xulosa) paragrafini ({level} darajasida, 2-4 gap) yozishni so'rang.",
        "conciseness": f"3-4 ta ORTIQCHA so'zlar bilan yozilgan (uzun, ortiqcha takrorli) gap yozing, nomzoddan ularni qisqa va lo'nda qilib qayta yozishni so'rang ({level} darajasiga mos).",
        "paraphrase": f"2-3 ta oddiy gap yozing, nomzoddan ularni boshqa so'zlar va tuzilma bilan, ma'nosini saqlab qayta ifodalashni (paraphrase) so'rang ({level} darajasiga mos).",
        "complex_sentence": f"3-4 ta oddiy (sodda) gap juftligini bering, nomzoddan ularni bog'lovchilar yordamida murakkab gaplarga birlashtirishni so'rang ({level} darajasiga mos).",
    }

    return f"""{base}
{specifics[skill_key]}

Faqat vazifa matnini yozing (aniq va qisqa), boshqa hech qanday izoh yoki
sarlavha qo'shmang."""


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
        temperature=0.7,
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


EXERCISE_SYSTEM = """Siz tajribali CEFR Writing o'qituvchisisiz. Original,
qisqa va aniq mashq vazifalari yaratasiz. Har safar boshqacha mavzu/gap
tanlang, takrorlamang.

MUHIM: Bu — INGLIZ TILI yozish mashqi. Vazifa ichidagi har qanday mavzu,
gap, misol yoki matn qismi (nomzod yozishi kerak bo'lgan yoki asos
qiladigan qism) albatta INGLIZ TILIDA bo'lishi kerak. Faqat vazifaning
o'zini tushuntiruvchi qisqa ko'rsatma (masalan "Quyidagi mavzu uchun...")
o'zbek tilida bo'lishi mumkin, lekin ingliz tilidagi mavzu/gap qismini
albatta kiriting."""


async def generate_exercise(skill_key: str, level: str) -> str:
    """Berilgan ko'nikma va daraja uchun qisqa mashq vazifasini generatsiya qiladi."""
    instruction = _build_exercise_instruction(skill_key, level)
    if LLM_PROVIDER == "anthropic":
        text = await _generate_anthropic(instruction, EXERCISE_SYSTEM)
    else:
        text = await _generate_gemini(instruction, EXERCISE_SYSTEM)
    return text.strip()


EVAL_SYSTEM = """Siz CEFR Writing o'qituvchisisiz. Nomzodning FAQAT bitta
aniq ko'nikma bo'yicha yozgan qisqa mashqini baholaysiz (butun insho emas,
faqat shu ko'nikma). Xolisona, konstruktiv va aniq baho bering.

Javobingizni FAQAT quyidagi JSON formatida bering:
{
  "score": <1 dan 5 gacha butun son>,
  "level_match": "<javob qaysi CEFR darajasiga to'g'ri keladi, masalan B1/B2/C1>",
  "strengths": ["<kuchli tomon 1>", "<kuchli tomon 2>"],
  "improvements": ["<yaxshilash kerak bo'lgan narsa 1>", "<...2>"],
  "improved_example": "<nomzod javobining yaxshilangan/tuzatilgan versiyasi, 1-3 gap>",
  "comment": "<2-3 gapdan iborat konstruktiv umumiy izoh, o'zbek tilida>"
}"""


def _build_eval_instruction(skill_key: str, level: str, exercise: str, user_text: str) -> str:
    skill = SKILLS[skill_key]["short"]
    return f"""Ko'nikma: {skill}
Maqsad daraja: {level}

VAZIFA (nomzodga berilgan):
{exercise}

NOMZODNING JAVOBI:
{user_text}

Yuqoridagi javobni "{skill}" ko'nikmasi nuqtai nazaridan, {level} darajasiga
mosligini hisobga olib baholang. Faqat JSON qaytaring."""


async def evaluate_skill_response(skill_key: str, level: str, exercise: str, user_text: str) -> dict:
    instruction = _build_eval_instruction(skill_key, level, exercise, user_text)
    if LLM_PROVIDER == "anthropic":
        client = _get_anthropic_client()
        response = await client.messages.create(
            model=CLAUDE_MODEL, max_tokens=800, system=EVAL_SYSTEM,
            messages=[{"role": "user", "content": instruction}],
        )
        raw = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    else:
        raw = await _generate_gemini(instruction, EVAL_SYSTEM, max_tokens=1200, json_mode=True)

    data = _extract_json(raw)
    score = data.get("score", 0)
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0
    data["score"] = max(1, min(5, score))
    return data
