# -*- coding: utf-8 -*-
"""
Telegram kanaliga avtomatik joylanadigan ta'lim kontenti:
  - Idiom (izoh + misollar + 4 ta test)
  - Phrasal verb (izoh + misollar + 4 ta test)
  - Grammatika darsi (A2+/B1/B2 aylanma tartibda + 4 ta test)

Kontent har safar Groq'ning bepul til modeli orqali YANGI generatsiya
qilinadi — cheksiz xilma-xillik uchun, oldindan yozilgan ro'yxat emas.
Testlar Telegram'ning o'z "quiz" turidagi so'rovnomasi (poll) orqali
yuboriladi — foydalanuvchi tugma bosib javob beradi, to'g'ri/noto'g'ri
avtomatik ko'rsatiladi.
"""
import json
import logging
import re
from datetime import date

from groq import AsyncGroq

from config import GROQ_API_KEY, GROQ_CHAT_MODEL
from idiom_bank import get_random_idiom
from phrasal_verb_bank import get_random_phrasal_verb
from idea_bank_topics import get_random_idea_topic
from morning_themes import get_random_morning_theme

logger = logging.getLogger(__name__)

client = AsyncGroq(api_key=GROQ_API_KEY)

GRAMMAR_LEVELS = ["B1", "B1+", "B2"]


def _extract_json(raw: str) -> dict:
    """Model javobidan JSON obyektini ajratib oladi, hatto model qo'shimcha
    matn yoki ortiqcha JSON qo'shib yuborgan bo'lsa ham ishlaydi."""
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    decoder = json.JSONDecoder()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    if start == -1:
        raise ValueError(f"Javobda JSON obyekti topilmadi: {raw[:200]!r}")
    obj, _ = decoder.raw_decode(raw, start)
    return obj


_JSON_FORMAT_INSTRUCTION = """
Javobingizni albatta FAQAT quyidagi JSON formatida bering, boshqa hech
qanday matn (izoh, sarlavha, ```json belgisi) qo'shmang:

{
  "title": "<mavzu sarlavhasi, o'zbek tilida>",
  "explanation": "<tushuntirish, o'zbek tilida, 3-6 gap, ingliz tilidagi asosiy so'z/ibora/qoidani o'z ichiga olgan holda>",
  "examples": ["<ingliz tilidagi misol gap 1>", "<ingliz tilidagi misol gap 2>", "<ingliz tilidagi misol gap 3>"],
  "quiz": [
    {
      "question": "<test savoli, o'zbek yoki ingliz tilida>",
      "options": ["<variant A>", "<variant B>", "<variant C>", "<variant D>"],
      "correct_index": <0, 1, 2 yoki 3>,
      "explanation": "<to'g'ri javob nima uchun to'g'ri ekanligi, JUDA QISQA, 1 gap, o'zbek tilida, 150 belgidan oshmasin>"
    }
  ]
}

"quiz" ro'yxatida ANIQ 4 ta savol bo'lishi shart. Har bir savolda ANIQ 4 ta
variant bo'lishi shart. Savollar mavzuni chuqur tushunishni tekshirsin
(faqat ta'rifni takrorlash emas, balki to'g'ri qo'llash, kontekstga mos
ma'no tanlash kabi turlarni aralashtiring).
"""

_VOCAB_EXTRA_FIELDS_INSTRUCTION = """
BUNDAN TASHQARI, yuqoridagi JSON obyektiga yana ikkita maydon QO'SHING:

  "transcription": "<so'z/ibora uchun IPA fonetik transkripsiya, "
                    "kvadrat qavslar bilan, masalan: /breɪk ðə aɪs/>",
  "definition_en": "<so'z/iboraning INGLIZ TILIDAGI lug'aviy ta'rifi, "
                    "lug'at uslubida, 1 qisqa gap, o'zbekcha tarjima "
                    "EMAS — masalan: 'to do or say something to make "
                    "people feel more relaxed in a social situation'>"

Bu ikkala maydon ham JSON obyektining eng yuqori darajasida ("title" va
"explanation" bilan bir qatorda) bo'lishi shart.
"""


async def _call_groq(system_prompt: str, user_prompt: str) -> dict:
    response = await client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        max_tokens=2000,
        temperature=0.9,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_text = response.choices[0].message.content
    return _extract_json(raw_text)


async def generate_idiom_lesson() -> dict:
    idiom, meaning_hint, level = get_random_idiom()
    system_prompt = (
        "Siz ingliz tili o'qituvchisiz. Sizga ANIQ BITTA ingliz idiomasi va "
        "uning inglizcha qisqa ma'nosi beriladi. Vazifangiz — shu ANIQ "
        "idioma ustida (boshqa idioma emas, aynan shu) o'zbek tilida "
        "tushunarli tushuntirish va 4 ta test savoli tuzish."
        + _JSON_FORMAT_INSTRUCTION + _VOCAB_EXTRA_FIELDS_INSTRUCTION
    )
    user_prompt = (
        f"Idioma: \"{idiom}\"\n"
        f"Inglizcha ma'nosi: {meaning_hint}\n\n"
        f"'title' maydoniga aynan shu idiomani va qavs ichida uning "
        f"o'zbekcha ma'nosini yozing, masalan: \"{idiom} (o'zbekcha ma'nosi)\". "
        f"'definition_en' maydoniga yuqoridagi inglizcha ma'noni lug'at "
        f"uslubida qayta ifodalab yozing. Boshqa idioma TAKLIF QILMANG — "
        f"faqat shu bitta idioma ustida ishlang."
    )
    data = await _call_groq(system_prompt, user_prompt)
    data["level"] = level
    return data


async def generate_phrasal_verb_lesson() -> dict:
    phrasal_verb, meaning_hint, level = get_random_phrasal_verb()
    system_prompt = (
        "Siz ingliz tili o'qituvchisiz. Sizga ANIQ BITTA ingliz phrasal "
        "verb'i va uning inglizcha qisqa ma'nosi beriladi. Vazifangiz — shu "
        "ANIQ phrasal verb ustida (boshqasi emas, aynan shu) o'zbek tilida "
        "tushunarli tushuntirish va 4 ta test savoli tuzish."
        + _JSON_FORMAT_INSTRUCTION + _VOCAB_EXTRA_FIELDS_INSTRUCTION
    )
    user_prompt = (
        f"Phrasal verb: \"{phrasal_verb}\"\n"
        f"Inglizcha ma'nosi: {meaning_hint}\n\n"
        f"'title' maydoniga aynan shu phrasal verb'ni va qavs ichida uning "
        f"o'zbekcha ma'nosini yozing, masalan: \"{phrasal_verb} (o'zbekcha ma'nosi)\". "
        f"'definition_en' maydoniga yuqoridagi inglizcha ma'noni lug'at "
        f"uslubida qayta ifodalab yozing. Boshqa phrasal verb TAKLIF QILMANG "
        f"— faqat shu bitta phrasal verb ustida ishlang."
    )
    data = await _call_groq(system_prompt, user_prompt)
    data["level"] = level
    return data


async def generate_grammar_lesson(level: str) -> dict:
    level_note = (
        " (B1+ — bu B1 va B2 orasidagi, B1 ni mustahkamlab, B2 ga o'tishga "
        "tayyorlaydigan oraliq daraja, ya'ni 'yuqori B1' mavzular ekanini "
        "hisobga oling)"
        if level == "B1+" else ""
    )
    system_prompt = (
        f"Siz ingliz tili o'qituvchisiz. Vazifangiz — CEFR {level} darajasiga "
        f"mos{level_note}, aniq bitta grammatik mavzuni tanlab, uni "
        "tushunarli, qisqa va aniq qilib tushuntirish (qoida + misollar), "
        "va shu mavzu ustida 4 ta test savoli tuzish."
        + _JSON_FORMAT_INSTRUCTION
        + "\n\nMUHIM: \"explanation\" maydonini O'ZBEK TILIDA EMAS, balki "
        "INGLIZ TILIDA yozing — bu grammatika qoidasi bo'lgani uchun, "
        "o'quvchi qoidani to'g'ridan-to'g'ri ingliz tilida o'qib "
        "tushunishi kerak. Grammatik terminlarni aniq va tushunarli, sodda "
        "ingliz tilida ishlating (masalan darslik uslubida)."
    )
    user_prompt = (
        f"CEFR {level} darajasiga mos ANIQ BITTA grammatik mavzuni tanlang "
        f"(masalan zamon turlari, artikllar, modal fe'llar, shart gaplar, "
        f"passiv nisbat va h.k. dan {level} darajaga mos keladiganini). "
        "'title' maydoniga mavzu nomini INGLIZ TILIDA yozing, "
        "masalan: \"Present Perfect vs Past Simple\"."
    )
    data = await _call_groq(system_prompt, user_prompt)
    data["level"] = level
    return data


def get_grammar_level_for_today() -> str:
    """Kunlar bo'yicha aylanma tartibda B1 -> B1+ -> B2 -> B1 ..."""
    day_index = date.today().toordinal()
    return GRAMMAR_LEVELS[day_index % len(GRAMMAR_LEVELS)]


async def generate_morning_greeting() -> str:
    """Kanal a'zolari uchun ertalabki, ingliz tilidagi salomlashish va ezgu
    tilaklar matnini generatsiya qiladi. Xilma-xillikni kafolatlash uchun
    har safar 45 talik bankdan TASODIFIY mavzu/burchak beriladi — AI
    o'zi erkin mavzu tanlamaydi, shu orqali bir xil umumiy shablonga
    ("Today is a new day...") qaytib qolish oldini oladi."""
    weekday = date.today().strftime("%A")
    theme = get_random_morning_theme()
    system_prompt = (
        "You are a warm, encouraging English teacher writing a short morning "
        "message for a Telegram channel of English learners (CEFR A2-C1). "
        "Write ONLY in English, in a natural, friendly and uplifting tone. "
        "Keep it SHORT: 3-5 sentences maximum. Include a warm greeting and a "
        "positive wish for the day, built around the SPECIFIC theme given to "
        "you (do not ignore it or replace it with a generic message). You "
        "may include 1-2 relevant emojis, but do not overuse them. Do NOT "
        "add any headings, labels, quotation marks around the whole text, "
        "or explanations — just the message itself."
    )
    user_prompt = (
        f"Today is {weekday}. Write today's morning greeting around this "
        f"SPECIFIC theme: \"{theme}\". Build the whole message naturally "
        f"around this exact theme — do not write a generic greeting."
    )

    response = await client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        max_tokens=400,
        temperature=1.0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()


async def generate_idea_bank() -> dict:
    """Speaking Part 3 va Writing Task 2 uchun fikr/argument boyitish
    materiali: lug'at, ijobiy/salbiy argumentlar va foydali ibora.
    Mavzu 90 talik bankdan TASODIFIY tanlanadi (AI o'zi mavzu tanlamaydi),
    shu orqali xilma-xillik kafolatlanadi va Speaking Part 3 / Writing
    Task 2 mavzulari bilan mos keladi."""
    topic = get_random_idea_topic()

    system_prompt = (
        "Siz CEFR Speaking va Writing imtihoniga tayyorlanuvchi o'quvchilar "
        "uchun material tayyorlovchi o'qituvchisiz. Sizga ANIQ BITTA bahsli "
        "mavzu beriladi. Vazifangiz — shu ANIQ mavzu bo'yicha (boshqa mavzu "
        "emas, aynan shu) o'quvchiga FIKR VA ARGUMENT boyitish uchun "
        "material tayyorlash (savol emas, imtihon vazifasi emas — "
        "shunchaki fikrlash uchun boy material).\n\n"
        "Javobingizni albatta FAQAT quyidagi JSON formatida bering, boshqa "
        "hech qanday matn qo'shmang:\n\n"
        "{\n"
        '  "topic": "<berilgan mavzu nomi, aynan shunday, inglizcha>",\n'
        '  "vocabulary": [\n'
        '    {"term": "<inglizcha so\'z/ibora>", "meaning": "<o\'zbekcha ma\'nosi>"}\n'
        "  ],\n"
        '  "arguments_for": ["<ingliz tilida argument 1>", "..."],\n'
        '  "arguments_against": ["<ingliz tilida argument 1>", "..."],\n'
        '  "useful_phrase": "<Speaking/Writingda ishlatsa bo\'ladigan tayyor "'
        'ingliz iborasi, masalan \'This raises serious concerns about...\'>"\n'
        "}\n\n"
        "\"vocabulary\" da ANIQ 5 ta element bo'lsin. \"arguments_for\" va "
        "\"arguments_against\" da ANIQ 3 tadan bo'lsin, har biri B2/C1 "
        "darajasiga mos, aniq va tushunarli yozilsin."
    )
    user_prompt = (
        f"Mavzu: \"{topic}\"\n\n"
        f"Ushbu ANIQ mavzu bo'yicha material tayyorlang. Boshqa mavzu "
        f"TAKLIF QILMANG — faqat shu mavzu ustida ishlang."
    )
    return await _call_groq(system_prompt, user_prompt)


def format_idea_bank_message(data: dict) -> str:
    vocab_lines = "\n".join(
        f"• <b>{v['term']}</b> — {v['meaning']}" for v in data.get("vocabulary", [])
    )
    for_lines = "\n".join(f"✅ {a}" for a in data.get("arguments_for", []))
    against_lines = "\n".join(f"⚠️ {a}" for a in data.get("arguments_against", []))

    return (
        f"💡 <b>Fikr banki: {data.get('topic', '')}</b>\n\n"
        f"<b>Foydali lug'at:</b>\n{vocab_lines}\n\n"
        f"<b>Argumentlar (rozi):</b>\n{for_lines}\n\n"
        f"<b>Argumentlar (qarshi):</b>\n{against_lines}\n\n"
        f"<b>Foydali ibora:</b>\n<i>\"{data.get('useful_phrase', '')}\"</i>\n\n"
        f"✍️ Bu materialdan Speaking Part 3 va Writing Task 2'da foydalaning!"
    )


def format_lesson_message(data: dict, emoji: str, kind_label: str) -> str:
    examples = "\n".join(f"• {ex}" for ex in data.get("examples", []))
    level_line = f" ({data['level']} daraja)" if "level" in data else ""

    extra_lines = ""
    if data.get("transcription"):
        extra_lines += f"🔊 {data['transcription']}\n"
    if data.get("definition_en"):
        extra_lines += f"📖 <i>{data['definition_en']}</i>\n"
    if extra_lines:
        extra_lines += "\n"

    return (
        f"{emoji} <b>{kind_label}{level_line}</b>\n\n"
        f"<b>{data['title']}</b>\n"
        f"{extra_lines}"
        f"{data['explanation']}\n\n"
        f"<b>Misollar:</b>\n{examples}\n\n"
        f"👇 Bilimingizni tekshiring — pastdagi 4 ta savolga javob bering!"
    )
