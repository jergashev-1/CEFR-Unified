"""
Transkriptni CEFR rubrikasi asosida baholash — Groq'ning BEPUL
til modeli orqali (kredit karta talab qilinmaydi).
"""
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_CHAT_MODEL

client = AsyncGroq(api_key=GROQ_API_KEY)


async def evaluate_transcript(
    transcript: str, rubric_text: str, questions: str = "", audio_metrics_summary: str = ""
) -> str:
    """
    Transkriptni berilgan qism-rubrikasi bo'yicha baholaydi va tayyor
    hisobotni qaytaradi.

    :param transcript: nomzod javoblarining matni
    :param rubric_text: shu qism (Part 1.1/1.2/2/3) uchun mos rubrika matni
        (rubric.get_rubric() orqali olinadi)
    :param questions: (ixtiyoriy) nomzodga berilgan savollar matni, kontekst uchun
    :param audio_metrics_summary: Whisper'dan olingan haqiqiy audio signallari
        (gapirish tezligi, pauzalar, filler so'zlar, va akustik ishonch
        ko'rsatkichlari avg_logprob/no_speech_prob). Akustik ishonch
        ko'rsatkichlari ovozning o'zidan (Whisper modeli orqali) olinadi,
        shuning uchun ular "Talaffuz" mezonini ham baholashda dalil sifatida
        ishlatiladi — lekin bu hali ham fonetik darajadagi aniq tahlil emas.
    :return: tayyorlangan baholash hisoboti (o'zbek tilida)
    """
    user_content = ""
    if questions:
        user_content += f"NOMZODGA BERILGAN SAVOLLAR:\n{questions}\n\n"
    if audio_metrics_summary:
        user_content += (
            "AUDIODAN O'LCHANGAN HAQIQIY SIGNALLAR (Whisper'dan, taxmin emas):\n"
            f"{audio_metrics_summary}\n\n"
            "Yuqoridagi 'gapirish tezligi', 'pauzalar', 'filler so'zlar' "
            "signallarini 'ravonlik' va 'ikkilanish' mezonlarida, 'avg_logprob' "
            "va 'past ishonchli segmentlar' ko'rsatkichlarini esa 'Talaffuz' "
            "mezonida asosiy dalil sifatida ishlating. Talaffuz bahosini "
            "berganda, bu fonetik darajadagi (qaysi tovush noto'g'ri "
            "talaffuz qilingani) aniq tahlil emasligini eslatib o'ting.\n\n"
        )
    user_content += f"NOMZOD JAVOBLARINING TRANSKRIPTI:\n{transcript}"

    response = await client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": rubric_text},
            {"role": "user", "content": user_content},
        ],
    )

    return response.choices[0].message.content
