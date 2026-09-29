# -*- coding: utf-8 -*-
"""
Multilevel CEFR Writing baholash boti.
Foydalanuvchi Task 1.1 / Task 1.2 / Task 2 dan birini tanlaydi,
matnini yuboradi, bot Claude API orqali CEFR mezonlari asosida baholaydi.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv

from evaluator import evaluate, generate_task_prompt
from rubrics import TASKS, get_standard_score
import db
import skills_practice as sp
import sentence_practice as sent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env fayliga qo'shing.")

# --- Webhook / Render sozlamalari ---
# Render.com "Web Service" yaratganda RENDER_EXTERNAL_URL o'zgaruvchisini avtomatik
# berishi kerak, lekin ba'zi holatlarda ishonchli bo'lmasligi mumkin — shuning uchun
# WEBHOOK_BASE_URL orqali ham qo'lda belgilash mumkin (Render Environment
# Variables'ga xizmatingiz manzilini, masalan https://writingevaluationbot.onrender.com,
# WEBHOOK_BASE_URL nomi bilan qo'shing). Ikkalasidan biri topilsa — webhook rejimi
# yoqiladi, aks holda (lokal kompyuterda) polling rejimi ishlaydi.
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = "/webhook"
USE_WEBHOOK = bool(WEBHOOK_BASE_URL)
PORT = int(os.getenv("PORT", "10000"))

# --- Donat sozlamalari ---
DONATE_CARD_NUMBER = os.getenv("DONATE_CARD_NUMBER", "8600 0000 0000 0000")
DONATE_CARD_HOLDER = os.getenv("DONATE_CARD_HOLDER", "F.I.Sh.")
DONATE_STAR_OPTIONS = [50, 100, 250, 500]  # Telegram Stars miqdorlari

# --- Vaqt bilan yozish (real imtihon) rejimi uchun vaqt chegaralari (daqiqa) ---
TASK_TIME_LIMITS = {"1.1": 20, "1.2": 20, "2": 40}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Foydalanuvchi ismlarini saqlaymiz (murojaat qilish uchun): {user_id: "Ism"}
user_names: dict[int, str] = {}
# Xatolikdan keyin "Qayta urinish" tugmasi uchun oxirgi yuborilgan matnni saqlaymiz:
# {user_id: {"task_key": ..., "text": ..., "start_time": datetime|None, "time_limit": int|None}}
user_last_submission: dict[int, dict] = {}


def get_display_name(user) -> str:
    """Foydalanuvchiga murojaat qilish uchun ismini qaytaradi."""
    if user.first_name:
        return user.first_name
    if user.username:
        return user.username
    return "Aziz foydalanuvchi"


def remember_user(user) -> str:
    """Foydalanuvchi ismini eslab qoladi va uni qaytaradi."""
    name = get_display_name(user)
    user_names[user.id] = name
    return name


class WritingStates(StatesGroup):
    waiting_for_text = State()


class SkillPracticeStates(StatesGroup):
    waiting_for_text = State()


class SentencePracticeStates(StatesGroup):
    waiting_for_text = State()


def main_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"✍️ Task 1.1 ({TASKS['1.1']['target_level']})", callback_data="task:1.1")],
        [InlineKeyboardButton(text=f"✍️ Task 1.2 ({TASKS['1.2']['target_level']})", callback_data="task:1.2")],
        [InlineKeyboardButton(text=f"✍️ Task 2 ({TASKS['2']['target_level']})", callback_data="task:2")],
        [InlineKeyboardButton(text="📚 Yozish mashqlari", callback_data="skills_menu")],
        [InlineKeyboardButton(text="🔤 Gap tuzish mashqlari", callback_data="sentence_menu")],
        [InlineKeyboardButton(text="📊 Natijalarni ko'rish", callback_data="results")],
        [InlineKeyboardButton(text="🙏 Botni qo'llab-quvvatlash", callback_data="donate_menu")],
        [InlineKeyboardButton(text="🔄 Qayta boshlash", callback_data="reset")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skills_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=skill["title"], callback_data=f"skill:{key}")]
        for key, skill in sp.SKILLS.items()
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skill_level_kb(skill_key: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=level, callback_data=f"skill_level:{skill_key}:{level}") for level in sp.LEVELS],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="skills_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skill_result_kb(skill_key: str, level: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔄 Yana mashq (shu ko'nikma)", callback_data=f"skill_level:{skill_key}:{level}")],
        [InlineKeyboardButton(text="📚 Boshqa ko'nikma", callback_data="skills_menu")],
        [InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sentence_level_kb() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=level, callback_data=f"sent_level:{level}")] for level in sent.LEVELS]
    buttons.append([InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sentence_type_kb(level: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=stype["title"], callback_data=f"sent_type:{level}:{key}")]
        for key, stype in sent.SENTENCE_TYPES.items()
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="sentence_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sentence_result_kb(level: str, sentence_type: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔄 Yana mashq (shu tur)", callback_data=f"sent_type:{level}:{sentence_type}")],
        [InlineKeyboardButton(text="🔤 Boshqa gap turi", callback_data=f"sent_level:{level}")],
        [InlineKeyboardButton(text="📶 Boshqa daraja", callback_data="sentence_menu")],
        [InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cancel")]]
    )


def mode_kb(task_key: str) -> InlineKeyboardMarkup:
    limit = TASK_TIME_LIMITS[task_key]
    buttons = [
        [InlineKeyboardButton(text="✍️ Oddiy (vaqt chegarasiz)", callback_data=f"mode:normal:{task_key}")],
        [InlineKeyboardButton(text=f"⏱️ Vaqt bilan ({limit} daqiqa)", callback_data=f"mode:timed:{task_key}")],
        [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def retry_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="retry_eval")]]
    )


def donate_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"⭐ {amount} Stars", callback_data=f"donate_stars:{amount}")]
        for amount in DONATE_STAR_OPTIONS
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def donate_text(name: str) -> str:
    return (
        f"🙏 <b>{name}, botni qo'llab-quvvatlash</b>\n\n"
        "Agar bot sizga foydali bo'lgan bo'lsa, uni qo'llab-quvvatlashingiz mumkin "
        "(bu ixtiyoriy, hech qanday qo'shimcha imkoniyat ochmaydi):\n\n"
        "⭐ <b>Telegram Stars</b> orqali — quyidagi tugmalardan birini bosing.\n\n"
        "💳 <b>Karta orqali</b>:\n"
        f"Karta raqami: <code>{DONATE_CARD_NUMBER}</code>\n"
        f"Karta egasi: {DONATE_CARD_HOLDER}\n\n"
        "Rahmat! ❤️"
    )


@dp.message(Command("donate"))
async def cmd_donate(message: Message):
    name = remember_user(message.from_user)
    await message.answer(donate_text(name), parse_mode="HTML", reply_markup=donate_kb())


@dp.callback_query(F.data == "donate_menu")
async def donate_menu(callback: CallbackQuery):
    name = remember_user(callback.from_user)
    await callback.message.edit_text(donate_text(name), parse_mode="HTML", reply_markup=donate_kb())
    await callback.answer()


@dp.callback_query(F.data.startswith("donate_stars:"))
async def donate_stars(callback: CallbackQuery):
    amount = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Botni qo'llab-quvvatlash",
        description=f"{amount} Telegram Stars — ixtiyoriy donat, hech qanday qo'shimcha imkoniyat ochmaydi.",
        payload=f"donate_{amount}",
        provider_token="",  # Telegram Stars uchun bo'sh qoldiriladi
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Stars donat", amount=amount)],
    )


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    name = remember_user(message.from_user)
    stars = message.successful_payment.total_amount
    await message.answer(
        f"✅ Rahmat, {name}! {stars} ⭐ Stars uchun donatingiz qabul qilindi. Sizga minnatdormiz! ❤️"
    )


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = remember_user(message.from_user)
    await message.answer(
        main_menu_text(name),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


def main_menu_text(name: str) -> str:
    return (
        f"Assalomu alaykum, {name}! 👋\n\n"
        "Bu bot <b>Multilevel CEFR Writing</b> vazifalarini baholaydi.\n"
        "Quyidagi vazifalardan birini tanlang va matningizni yuboring:\n\n"
        f"• <b>Task 1.1</b> — norasmiy email ({TASKS['1.1']['word_range']}, maqsad daraja B1)\n"
        f"• <b>Task 1.2</b> — rasmiy email ({TASKS['1.2']['word_range']}, maqsad daraja B2)\n"
        f"• <b>Task 2</b> — blog/forum posti ({TASKS['2']['word_range']}, maqsad daraja C1)\n"
        "• <b>📚 Yozish mashqlari</b> — Introduction, Body, Conclusion va boshqa ko'nikmalarni alohida mashq qiling\n"
        "• <b>🔤 Gap tuzish mashqlari</b> — Simple/Compound/Complex gaplar va bog'lovchilarni B1-C1 darajasida mashq qiling\n\n"
        "Botni yoqtirsangiz, /donate orqali qo'llab-quvvatlashingiz mumkin 🙏"
    )


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    name = remember_user(callback.from_user)
    await callback.message.edit_text(main_menu_text(name), reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("task:"))
async def choose_task(callback: CallbackQuery, state: FSMContext):
    remember_user(callback.from_user)
    task_key = callback.data.split(":", 1)[1]
    await state.update_data(task_key=task_key)
    task = TASKS[task_key]
    limit = TASK_TIME_LIMITS[task_key]
    await callback.message.edit_text(
        f"📝 <b>{task['title']}</b>\n"
        f"Tavsiya etilgan hajm: {task['word_range']}\n\n"
        f"Qanday rejimda yozmoqchisiz?\n"
        f"• <b>Oddiy</b> — vaqt chegarasisiz, o'z sur'atingizda.\n"
        f"• <b>Vaqt bilan</b> — real imtihon kabi, {limit} daqiqa ichida yozib ulgurishga harakat qilasiz "
        f"(vaqtingiz tugagach ham yozishni davom ettirishingiz mumkin, shunchaki natijada sarflangan vaqt ko'rsatiladi).",
        parse_mode="HTML",
        reply_markup=mode_kb(task_key),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("mode:"))
async def choose_mode(callback: CallbackQuery, state: FSMContext):
    name = remember_user(callback.from_user)
    _, mode, task_key = callback.data.split(":", 2)
    task = TASKS[task_key]
    timed = mode == "timed"
    limit = TASK_TIME_LIMITS[task_key]

    await callback.message.edit_text(f"⏳ {name}, sizga original mavzu tayyorlanmoqda...")
    await callback.answer()

    try:
        task_prompt = await generate_task_prompt(task_key)
        word_count = len(task_prompt.split()) if task_prompt else 0
        logger.info("Generatsiya qilingan mavzu (%d so'z): %r", word_count, task_prompt)
        if not task_prompt or word_count < 15:
            # Juda qisqa/noto'liq javob — muvaffaqiyatsiz deb hisoblaymiz
            task_prompt = None
    except Exception:
        logger.exception("Mavzu generatsiyasida xatolik")
        task_prompt = None

    # Vaqt bilan rejimda timer aynan shu yerdan, mavzu ko'rsatilgandan keyin boshlanadi
    start_time = datetime.now().isoformat() if timed else None
    await state.update_data(
        task_key=task_key,
        timed=timed,
        start_time=start_time,
        time_limit=limit if timed else None,
        task_prompt=task_prompt,
    )
    await state.set_state(WritingStates.waiting_for_text)

    header = (
        f"⏱️ <b>{task['title']} — Vaqt bilan rejim</b>\n"
        f"Vaqt chegarasi: <b>{limit} daqiqa</b> (taxminan {(datetime.now() + timedelta(minutes=limit)).strftime('%H:%M')} gacha)\n"
        if timed
        else f"📝 <b>{task['title']}</b>\n"
    )
    prompt_block = f"\n📋 <b>Mavzu:</b>\n{task_prompt}\n" if task_prompt else "\n(Mavzu generatsiya qilinmadi — o'zingiz mos mavzu tanlab yozishingiz mumkin.)\n"
    footer = f"\nTavsiya etilgan hajm: {task['word_range']}\n\n{name}, endi javob matningizni <b>bitta xabar</b> tarzida yuboring."
    if timed:
        footer = f"\nTavsiya etilgan hajm: {task['word_range']}\n\n{name}, timer boshlandi! ⏳ Endi javob matningizni <b>bitta xabar</b> tarzida yuboring."

    text = header + prompt_block + footer
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb())


@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.", reply_markup=main_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "reset")
async def reset(callback: CallbackQuery, state: FSMContext):
    name = remember_user(callback.from_user)
    await state.clear()
    await callback.message.edit_text(
        f"{name}, yangi urinish boshlashingiz mumkin (oldingi natijalaringiz tarixda saqlanib qoladi).",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@dp.callback_query(F.data == "results")
async def show_results(callback: CallbackQuery):
    remember_user(callback.from_user)
    await callback.answer()
    await send_results(callback.message.chat.id, callback.from_user.id)


async def send_results(chat_id: int, user_id: int):
    name = user_names.get(user_id, "Siz")
    try:
        latest = await db.get_latest_results(user_id)
    except Exception:
        logger.exception("Bazadan natijalarni olishda xatolik")
        await bot.send_message(chat_id, f"{name}, natijalarni yuklashda texnik xatolik yuz berdi.", reply_markup=main_menu_kb())
        return

    if not latest:
        await bot.send_message(chat_id, f"{name}, hozircha natijalar yo'q. Avval vazifalardan birini bajaring.", reply_markup=main_menu_kb())
        return

    lines = [f"📊 <b>{name}, natijalaringiz</b>\n"]
    raw_sum = 0
    all_done = True
    for key in ("1.1", "1.2", "2"):
        task = TASKS[key]
        if key in latest:
            row = latest[key]
            score = row["score"]
            level = row.get("estimated_level") or "—"
            raw_sum += score
            lines.append(f"• {task['title']}: <b>{score}/{task['max_score']}</b> (~{level})")
        else:
            all_done = False
            lines.append(f"• {task['title']}: bajarilmagan")

    if all_done:
        std_score = get_standard_score(raw_sum)
        lines.append(f"\n🎯 Jami (Expert bahosi): <b>{raw_sum}/16</b>")
        lines.append(f"🏁 Standard ball: <b>{std_score}/75</b>")
        lines.append(f"\nTabriklaymiz, {name}! 🎉")
    else:
        lines.append("\nYakuniy Standard ball uchun barcha 3 ta vazifani bajaring.")

    await bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML", reply_markup=main_menu_kb())


def format_elapsed(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


async def run_evaluation(chat_id: int, user_id: int, name: str, task_key: str, text: str, timed_info: dict, status_message: Message, task_prompt: str | None = None):
    """Matnni baholaydi (vaqtinchalik xatolarda 1 marta avtomatik qayta urinadi),
    natijani status_message orqali ko'rsatadi. Muvaffaqiyatsiz bo'lsa, "Qayta urinish"
    tugmasi bilan xabar qoldiradi."""
    result = None
    last_error = None
    for attempt in range(2):  # 1-urinish + 1-avtomatik qayta urinish
        try:
            result = await evaluate(task_key, text, custom_prompt=task_prompt)
            break
        except Exception as e:
            last_error = e
            logger.exception("Baholashda xatolik (urinish %s)", attempt + 1)
            if attempt == 0:
                await asyncio.sleep(2)

    if result is None:
        user_last_submission[user_id] = {"task_key": task_key, "text": text, "task_prompt": task_prompt, **timed_info}
        await status_message.edit_text(
            f"⚠️ {name}, baholashda texnik xatolik yuz berdi: {last_error}\n"
            "Bu odatda vaqtinchalik holat (server band). Quyidagi tugma orqali qayta urinib ko'ring.",
            reply_markup=retry_kb(),
        )
        return

    user_last_submission.pop(user_id, None)
    try:
        await db.save_result(
            user_id=user_id,
            user_name=name,
            task_key=task_key,
            score=result["score"],
            max_score=TASKS[task_key]["max_score"],
            estimated_level=result.get("estimated_cefr_level"),
            comment=result.get("comment"),
        )
    except Exception:
        logger.exception("Natijani bazaga saqlashda xatolik")

    task = TASKS[task_key]
    strengths = "\n".join(f"  ✅ {s}" for s in result.get("strengths", [])) or "  —"
    improvements = "\n".join(f"  🔧 {s}" for s in result.get("improvements", [])) or "  —"

    time_line = ""
    if timed_info.get("timed") and timed_info.get("start_time"):
        start_time = datetime.fromisoformat(timed_info["start_time"])
        elapsed = (datetime.now() - start_time).total_seconds()
        limit_sec = timed_info["time_limit"] * 60
        status = "✅ Vaqtida yakunladingiz" if elapsed <= limit_sec else f"⚠️ Vaqtdan {format_elapsed(elapsed - limit_sec)} ga oshirib yubordingiz"
        time_line = f"⏱️ Sarflangan vaqt: <b>{format_elapsed(elapsed)}</b> (chegarasi {timed_info['time_limit']} daq) — {status}\n"

    text_out = (
        f"📝 <b>{task['title']}</b>\n"
        f"{name}, ballingiz: <b>{result['score']}/{task['max_score']}</b>\n"
        f"Taxminiy daraja: <b>{result.get('estimated_cefr_level', '—')}</b>\n"
        f"{time_line}"
        f"So'zlar soni: {result.get('word_count_comment', '—')}\n\n"
        f"<u>Kuchli tomonlari:</u>\n{strengths}\n\n"
        f"<u>Yaxshilash kerak:</u>\n{improvements}\n\n"
        f"💬 {result.get('comment', '')}"
    )
    await status_message.edit_text(text_out, parse_mode="HTML")
    await send_results(chat_id, user_id)


@dp.message(WritingStates.waiting_for_text, F.text)
async def receive_text(message: Message, state: FSMContext):
    name = remember_user(message.from_user)
    data = await state.get_data()
    task_key = data.get("task_key")
    if not task_key:
        await state.clear()
        await message.answer(f"{name}, xatolik yuz berdi, qaytadan boshlang.", reply_markup=main_menu_kb())
        return

    timed_info = {
        "timed": data.get("timed", False),
        "start_time": data.get("start_time"),
        "time_limit": data.get("time_limit"),
    }
    task_prompt = data.get("task_prompt")
    await state.clear()

    thinking = await message.answer(f"⏳ {name}, matningiz baholanmoqda, biroz kuting...")
    await run_evaluation(message.chat.id, message.from_user.id, name, task_key, message.text, timed_info, thinking, task_prompt)


@dp.callback_query(F.data == "retry_eval")
async def retry_eval(callback: CallbackQuery):
    name = remember_user(callback.from_user)
    pending = user_last_submission.get(callback.from_user.id)
    if not pending:
        await callback.answer("Qayta urinish uchun ma'lumot topilmadi, qaytadan yozing.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(f"⏳ {name}, qayta urinilmoqda...")
    timed_info = {
        "timed": pending.get("timed", False),
        "start_time": pending.get("start_time"),
        "time_limit": pending.get("time_limit"),
    }
    await run_evaluation(
        callback.message.chat.id, callback.from_user.id, name,
        pending["task_key"], pending["text"], timed_info, callback.message,
        pending.get("task_prompt"),
    )


@dp.message(WritingStates.waiting_for_text)
async def receive_non_text(message: Message):
    name = remember_user(message.from_user)
    await message.answer(f"{name}, bot faqat matn bilan ishlaydi. Iltimos, javobingizni matn shaklida yuboring.")


# ---------------------------------------------------------------------------
# Yozish mashqlari (Introduction, Body, Conclusion, Conciseness, Paraphrase,
# Complex sentences) — alohida ko'nikmalarni CEFR darajasiga mos mashq qilish
# ---------------------------------------------------------------------------

@dp.callback_query(F.data == "skills_menu")
async def skills_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    name = remember_user(callback.from_user)
    await callback.message.edit_text(
        f"📚 <b>{name}, yozish mashqlari</b>\n\n"
        "Qaysi ko'nikmani mashq qilmoqchisiz? Har biri uchun avval qisqa "
        "nazariy tushuntirish, keyin amaliy mashq beriladi.",
        parse_mode="HTML",
        reply_markup=skills_menu_kb(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("skill:"))
async def choose_skill(callback: CallbackQuery, state: FSMContext):
    remember_user(callback.from_user)
    skill_key = callback.data.split(":", 1)[1]
    skill = sp.SKILLS[skill_key]
    await callback.message.edit_text(
        f"{skill['title']}\n\nQaysi CEFR darajasida mashq qilmoqchisiz?",
        reply_markup=skill_level_kb(skill_key),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("skill_level:"))
async def choose_skill_level(callback: CallbackQuery, state: FSMContext):
    name = remember_user(callback.from_user)
    _, skill_key, level = callback.data.split(":", 2)
    skill = sp.SKILLS[skill_key]
    theory = sp.STATIC_THEORY[skill_key]

    await callback.message.edit_text(f"{theory}\n\n⏳ Mashq tayyorlanmoqda...", parse_mode="HTML")
    await callback.answer()

    try:
        exercise = await sp.generate_exercise(skill_key, level)
        if not exercise or len(exercise.split()) < 5:
            exercise = None
    except Exception:
        logger.exception("Mashq generatsiyasida xatolik")
        exercise = None

    if not exercise:
        await callback.message.edit_text(
            f"{theory}\n\n⚠️ {name}, mashq generatsiya qilinmadi (server band bo'lishi mumkin). "
            "Qaytadan urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=skill_level_kb(skill_key),
        )
        return

    await state.update_data(skill_key=skill_key, level=level, exercise=exercise)
    await state.set_state(SkillPracticeStates.waiting_for_text)

    await callback.message.edit_text(
        f"{theory}\n\n"
        f"📝 <b>Mashq ({level}):</b>\n{exercise}\n\n"
        f"{name}, javobingizni bitta xabar tarzida yuboring.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="skills_menu")]]
        ),
    )


@dp.message(SkillPracticeStates.waiting_for_text, F.text)
async def receive_skill_text(message: Message, state: FSMContext):
    name = remember_user(message.from_user)
    data = await state.get_data()
    skill_key = data.get("skill_key")
    level = data.get("level")
    exercise = data.get("exercise")
    await state.clear()

    if not skill_key:
        await message.answer(f"{name}, xatolik yuz berdi, qaytadan boshlang.", reply_markup=main_menu_kb())
        return

    thinking = await message.answer(f"⏳ {name}, javobingiz tekshirilmoqda...")

    result = None
    last_error = None
    for attempt in range(2):
        try:
            result = await sp.evaluate_skill_response(skill_key, level, exercise, message.text)
            break
        except Exception as e:
            last_error = e
            logger.exception("Ko'nikma baholashda xatolik (urinish %s)", attempt + 1)
            if attempt == 0:
                await asyncio.sleep(2)

    if result is None:
        await thinking.edit_text(
            f"⚠️ {name}, tekshirishda texnik xatolik yuz berdi: {last_error}\nQaytadan urinib ko'ring.",
            reply_markup=skill_level_kb(skill_key),
        )
        return

    skill = sp.SKILLS[skill_key]
    strengths = "\n".join(f"  ✅ {s}" for s in result.get("strengths", [])) or "  —"
    improvements = "\n".join(f"  🔧 {s}" for s in result.get("improvements", [])) or "  —"
    improved = result.get("improved_example", "")

    text_out = (
        f"{skill['title']} — natija\n"
        f"{name}, ball: <b>{result['score']}/5</b>\n"
        f"Mos daraja: <b>{result.get('level_match', '—')}</b>\n\n"
        f"<u>Kuchli tomonlari:</u>\n{strengths}\n\n"
        f"<u>Yaxshilash kerak:</u>\n{improvements}\n\n"
        + (f"<u>Yaxshilangan namuna:</u>\n<i>{improved}</i>\n\n" if improved else "")
        + f"💬 {result.get('comment', '')}"
    )
    await thinking.edit_text(text_out, parse_mode="HTML", reply_markup=skill_result_kb(skill_key, level))


@dp.message(SkillPracticeStates.waiting_for_text)
async def receive_skill_non_text(message: Message):
    name = remember_user(message.from_user)
    await message.answer(f"{name}, bot faqat matn bilan ishlaydi. Iltimos, javobingizni matn shaklida yuboring.")


# ---------------------------------------------------------------------------
# Gap tuzish mashqlari (Simple/Compound/Complex/Compound-Complex, B1-C1)
# ---------------------------------------------------------------------------

@dp.callback_query(F.data == "sentence_menu")
async def sentence_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    name = remember_user(callback.from_user)
    await callback.message.edit_text(
        f"🔤 <b>{name}, gap tuzish mashqlari</b>\n\n"
        "Qaysi CEFR darajasida mashq qilmoqchisiz? Har bir darajada mos "
        "bog'lovchilar bilan Simple, Compound, Complex va Compound-Complex "
        "gaplarni mashq qilasiz.",
        parse_mode="HTML",
        reply_markup=sentence_level_kb(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sent_level:"))
async def choose_sentence_level(callback: CallbackQuery, state: FSMContext):
    remember_user(callback.from_user)
    level = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        f"Daraja: <b>{level}</b>\n\nQaysi gap turini mashq qilmoqchisiz?",
        parse_mode="HTML",
        reply_markup=sentence_type_kb(level),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sent_type:"))
async def choose_sentence_type(callback: CallbackQuery, state: FSMContext):
    name = remember_user(callback.from_user)
    _, level, sentence_type = callback.data.split(":", 2)
    stype = sent.SENTENCE_TYPES[sentence_type]
    theory = sent.STATIC_THEORY[sentence_type]
    connectors = sent.connectors_line(level)

    await callback.message.edit_text(f"{theory}\n\n{connectors}\n\n⏳ Mashq tayyorlanmoqda...", parse_mode="HTML")
    await callback.answer()

    try:
        exercise = await sent.generate_sentence_exercise(level, sentence_type)
        if not exercise or len(exercise.split()) < 3:
            exercise = None
    except Exception:
        logger.exception("Gap mashqi generatsiyasida xatolik")
        exercise = None

    if not exercise:
        await callback.message.edit_text(
            f"{theory}\n\n{connectors}\n\n⚠️ {name}, mashq generatsiya qilinmadi (server band bo'lishi mumkin). "
            "Qaytadan urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=sentence_type_kb(level),
        )
        return

    await state.update_data(level=level, sentence_type=sentence_type, exercise=exercise)
    await state.set_state(SentencePracticeStates.waiting_for_text)

    await callback.message.edit_text(
        f"{theory}\n\n{connectors}\n\n"
        f"📝 <b>Mashq — {stype['title']} ({level}):</b>\n{exercise}\n\n"
        f"{name}, javobingizni bitta xabar tarzida yuboring.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="sentence_menu")]]
        ),
    )


@dp.message(SentencePracticeStates.waiting_for_text, F.text)
async def receive_sentence_text(message: Message, state: FSMContext):
    name = remember_user(message.from_user)
    data = await state.get_data()
    level = data.get("level")
    sentence_type = data.get("sentence_type")
    exercise = data.get("exercise")
    await state.clear()

    if not level:
        await message.answer(f"{name}, xatolik yuz berdi, qaytadan boshlang.", reply_markup=main_menu_kb())
        return

    thinking = await message.answer(f"⏳ {name}, javobingiz tekshirilmoqda...")

    result = None
    last_error = None
    for attempt in range(2):
        try:
            result = await sent.evaluate_sentence_response(level, sentence_type, exercise, message.text)
            break
        except Exception as e:
            last_error = e
            logger.exception("Gap baholashda xatolik (urinish %s)", attempt + 1)
            if attempt == 0:
                await asyncio.sleep(2)

    if result is None:
        await thinking.edit_text(
            f"⚠️ {name}, tekshirishda texnik xatolik yuz berdi: {last_error}\nQaytadan urinib ko'ring.",
            reply_markup=sentence_type_kb(level),
        )
        return

    stype = sent.SENTENCE_TYPES[sentence_type]
    correct_mark = "✅ To'g'ri gap turi" if result.get("is_correct_type") else f"❌ Bu {result.get('detected_type', 'boshqa')} gap, so'ralgan tur emas"
    connectors_used = ", ".join(result.get("connectors_used", [])) or "—"
    errors = "\n".join(f"  🔧 {e}" for e in result.get("grammar_errors", [])) or "  — (xato topilmadi)"
    corrected = result.get("corrected_version", "")

    text_out = (
        f"{stype['title']} — natija ({level})\n"
        f"{name}, ball: <b>{result['score']}/5</b>\n"
        f"{correct_mark}\n"
        f"Ishlatilgan bog'lovchi(lar): <i>{connectors_used}</i>\n"
        f"💡 {result.get('connector_feedback', '')}\n\n"
        f"<u>Xatolar va tushuntirish:</u>\n{errors}\n\n"
        + (f"<u>To'g'irlangan versiya:</u>\n<i>{corrected}</i>\n\n" if corrected else "")
        + f"💬 {result.get('comment', '')}"
    )
    await thinking.edit_text(text_out, parse_mode="HTML", reply_markup=sentence_result_kb(level, sentence_type))


@dp.message(SentencePracticeStates.waiting_for_text)
async def receive_sentence_non_text(message: Message):
    name = remember_user(message.from_user)
    await message.answer(f"{name}, bot faqat matn bilan ishlaydi. Iltimos, javobingizni matn shaklida yuboring.")


@dp.message()
async def fallback(message: Message):
    name = remember_user(message.from_user)
    await message.answer(f"{name}, vazifani tanlash uchun /start buyrug'ini yuboring.", reply_markup=main_menu_kb())


async def main():
    await db.init_db()
    logger.info("Baza tayyor")

    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Bosh menyu"),
        BotCommand(command="donate", description="🙏 Botni qo'llab-quvvatlash"),
    ])
    logger.info("Bot buyruqlari (Menu) o'rnatildi")

    if USE_WEBHOOK:
        # --- Render.com uchun: webhook rejimi ---
        webhook_url = WEBHOOK_BASE_URL.rstrip("/") + WEBHOOK_PATH
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logger.info(f"Webhook o'rnatildi: {webhook_url}")

        app = web.Application()

        async def health(request):
            return web.Response(text="OK")

        app.router.add_get("/", health)
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
        await site.start()
        logger.info(f"Web server {PORT}-portda ishga tushdi (webhook rejimi)")

        # Server ochiq turishi uchun cheksiz kutamiz
        await asyncio.Event().wait()
    else:
        # --- Lokal kompyuterda: polling rejimi ---
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
