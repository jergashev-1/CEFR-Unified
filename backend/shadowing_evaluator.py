# -*- coding: utf-8 -*-
"""
Shadowing mashqini baholash: nomzod aytgan gapni (Whisper orqali matnga
aylantirilgan) maqsad jumla bilan so'z darajasida solishtiradi (aniqlik
foizini hisoblaydi) va Groq LLM orqali talaffuz/ravonlikka oid qisqa,
konstruktiv fikr-mulohaza yozdiradi.
"""
import difflib
import re

from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_CHAT_MODEL

client = AsyncGroq(api_key=GROQ_API_KEY)


def _normalize_words(text: str) -> list:
    text = text.lower()
    text = re.sub(r"[^\w\s']", "", text)
    return text.split()


def compare_texts(target_text: str, transcript: str) -> dict:
    """Maqsad jumla va nomzod aytgan matnni so'z darajasida solishtiradi.

    :return: {
        "accuracy_percent": 0-100,
        "words": [{"word": ..., "status": "match"|"missed"|"extra"}, ...]
    }
    """
    target_words = _normalize_words(target_text)
    said_words = _normalize_words(transcript)

    matcher = difflib.SequenceMatcher(a=target_words, b=said_words)
    accuracy = round(matcher.ratio() * 100)

    annotated = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for w in target_words[i1:i2]:
                annotated.append({"word": w, "status": "match"})
        elif tag == "replace":
            for w in target_words[i1:i2]:
                annotated.append({"word": w, "status": "missed"})
            for w in said_words[j1:j2]:
                annotated.append({"word": w, "status": "extra"})
        elif tag == "delete":
            for w in target_words[i1:i2]:
                annotated.append({"word": w, "status": "missed"})
        elif tag == "insert":
            for w in said_words[j1:j2]:
                annotated.append({"word": w, "status": "extra"})

    return {"accuracy_percent": accuracy, "words": annotated}


SHADOWING_SYSTEM_PROMPT = """Siz talaffuz (pronunciation) va ravonlik
(fluency) bo'yicha tajribali til o'qituvchisiz. Nomzod "shadowing" mashqini
bajardi: unga inglizcha bir jumla ko'rsatilgan/eshittirilgan, u shu jumlani
takrorlab, ovozli yozib olgan.

Sizga quyidagilar beriladi:
- Maqsad jumla (nomzod nima deyishi kerak edi)
- Nomzod aytgan jumlaning transkripti (Whisper orqali)
- So'z darajasidagi aniqlik foizi
- Audio signallari (gapirish tezligi, pauzalar, akustik ishonch darajasi)

Vazifangiz: 2-4 gapdan iborat, QISQA va KONSTRUKTIV fikr-mulohaza yozish
(o'zbek tilida). E'tiboringizni quyidagilarga qarating:
- Agar so'zlar tushirilgan/almashtirilgan bo'lsa, buni aytib o'ting
- Agar gapirish tezligi juda sekin yoki juda tez bo'lsa, buni aytib o'ting
- Agar audio signallari (past avg_logprob) talaffuz noaniqligini ko'rsatsa,
  buni aytib o'ting, lekin bu FONETIK aniq tahlil emasligini eslating
- Nomzodni rag'batlantiruvchi ohangda yozing, lekin halol baho bering

Faqat oddiy matn yozing, yulduzcha yoki boshqa formatlash belgilarisiz."""


async def evaluate_shadowing(
    target_text: str, transcript: str, accuracy_percent: int, audio_metrics_summary: str = ""
) -> str:
    user_content = (
        f"MAQSAD JUMLA:\n{target_text}\n\n"
        f"NOMZOD AYTGAN JUMLA (transkript):\n{transcript}\n\n"
        f"SO'Z DARAJASIDAGI ANIQLIK: {accuracy_percent}%\n\n"
    )
    if audio_metrics_summary:
        user_content += f"AUDIO SIGNALLARI:\n{audio_metrics_summary}\n"

    response = await client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        max_tokens=400,
        messages=[
            {"role": "system", "content": SHADOWING_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content
