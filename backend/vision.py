"""
Rasm orqali yuborilgan imtihon materialini o'qish/tushunish — Groq'ning
bepul vizual (vision) modeli orqali. (Foydalanuvchining ishlab turgan
Speaking botidan olingan, o'zgarishsiz.)
"""
import base64

from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_VISION_MODEL

client = AsyncGroq(api_key=GROQ_API_KEY)

_PROMPT = (
    "Bu rasm CEFR Multilevel Speaking imtihoni uchun materialdir. Unda "
    "ikki xil narsa bo'lishi mumkin: (a) chop etilgan savol matni "
    "(masalan bullet-point savollar), va/yoki (b) nomzod OG'ZAKI "
    "TASVIRLASHI kerak bo'lgan fotosurat(lar).\n\n"
    "Quyidagi ikki bo'limda javob bering:\n\n"
    "SAVOLLAR:\n"
    "Rasmdagi barcha chop etilgan savol matnini aniq va to'liq o'qib, "
    "har birini alohida qatorda yozing. Agar chop etilgan savol matni "
    "umuman bo'lmasa, 'Yo'q' deb yozing.\n\n"
    "RASMLARDAGI TASVIR:\n"
    "Agar rasm ichida fotosurat(lar) mavjud bo'lsa, har biri haqida "
    "batafsil tasvir bering — kim/nima ko'rinadi, ular nima qilyapti, "
    "qayerda, qanday muhit/holat. Agar bir nechta fotosurat bo'lsa, "
    "ularni '1-rasm:', '2-rasm:' deb ajratib tasvirlang. Agar rasm faqat "
    "matndan iborat bo'lib, alohida fotosurat bo'lmasa, 'Yo'q' deb yozing.\n\n"
    "Boshqa hech qanday qo'shimcha izoh yozmang, faqat shu ikki bo'lim."
)


async def extract_question_from_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        image_bytes = f.read()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = await client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        max_tokens=800,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()


_DESCRIBE_URL_PROMPT = (
    "Ushbu fotosuratda nima tasvirlanganini batafsil tasvirlab bering — "
    "kim/nima ko'rinadi, ular nima qilyapti, qayerda, qanday muhit/holat. "
    "2-3 gap yetarli. Faqat tasvirni yozing, boshqa izoh qo'shmang."
)


async def describe_image_url(image_url: str) -> str:
    response = await client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _DESCRIBE_URL_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()
