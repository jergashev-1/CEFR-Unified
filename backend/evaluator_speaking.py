"""
Transkriptni CEFR rubrikasi asosida baholash — Groq'ning BEPUL
til modeli orqali. (Foydalanuvchining ishlab turgan Speaking botidan
olingan, o'zgarishsiz.)
"""
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_CHAT_MODEL

client = AsyncGroq(api_key=GROQ_API_KEY)


async def evaluate_transcript(
    transcript: str, rubric_text: str, questions: str = "", audio_metrics_summary: str = ""
) -> str:
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
            "berganda, bu fonetik darajadagi aniq tahlil emasligini eslatib o'ting.\n\n"
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
