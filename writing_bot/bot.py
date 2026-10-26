# -*- coding: utf-8 -*-
"""
Multilevel CEFR Writing baholash boti.
Foydalanuvchi Task 1.1 / Task 1.2 / Task 2 dan birini tanlaydi,
matnini yuboradi, bot Claude API orqali CEFR mezonlari asosida baholaydi.
"""
import asyncio
import random
import html
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    WebAppInfo,
    FSInputFile,
)
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv

from evaluator import evaluate, generate_task_prompt
from rubrics import TASKS, get_standard_score
from products import PRODUCTS, build_shop_keyboard, build_admin_approval_kb, get_material_path
import db

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env fayliga qo'shing.")

# --- Sayt manzili (Telegram Mini App / Web App tugmasi uchun) ---
# Bu yerga Netlify'dagi saytingizning manzilini yozing. ?tab=writing qismi
# sayt ochilganda avtomatik Writing bo'limini ko'rsatadi.
WRITING_SITE_URL = os.getenv(
    "WRITING_SITE_URL",
    "https://cefr-multilevel-test-speaking-writing.netlify.app/?tab=writing",
)

# --- Ta'lim kanali (Speaking botdagi @english4y kanali bilan bir xil) ---
# Test tugagach, foydalanuvchini kanalga taklif qilish uchun ishlatiladi.
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

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

# --- Do'kon: admin ID (karta orqali to'lovlarni tasdiqlash uchun) ---
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "817610690"))

# Karta orqali to'lov kutilayotgan buyurtmalar: {user_id: product_id}
# (RAMda saqlanadi; bot qayta ishga tushirilsa tozalanadi)
pending_card_orders: dict[int, str] = {}

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


def main_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🌐 Saytda test topshirish", url=WRITING_SITE_URL)],
        [InlineKeyboardButton(text=f"✍️ Task 1.1 ({TASKS['1.1']['target_level']})", callback_data="task:1.1")],
        [InlineKeyboardButton(text=f"✍️ Task 1.2 ({TASKS['1.2']['target_level']})", callback_data="task:1.2")],
        [InlineKeyboardButton(text=f"✍️ Task 2 ({TASKS['2']['target_level']})", callback_data="task:2")],
        [InlineKeyboardButton(text="📊 Natijalarni ko'rish", callback_data="results")],
        [InlineKeyboardButton(text="🛒 Materiallar do'koni", callback_data="shop")],
        [InlineKeyboardButton(text="🙏 Botni qo'llab-quvvatlash", callback_data="donate")],
        [InlineKeyboardButton(text="🔄 Qayta boshlash", callback_data="reset")],
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
    await message.answer(
        donate_text(name),
        parse_mode="HTML",
        reply_markup=donate_kb(),
    )


@dp.callback_query(F.data == "donate")
async def donate_button(callback: CallbackQuery):
    name = remember_user(callback.from_user)
    await callback.answer()
    await callback.message.answer(
        donate_text(name),
        parse_mode="HTML",
        reply_markup=donate_kb(),
    )



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


# ---------------------------------------------------------------------------
# DO'KON: materiallar (handout/worksheet) sotish — Telegram Stars orqali
# ---------------------------------------------------------------------------
@dp.callback_query(F.data == "shop")
async def shop_open(callback: CallbackQuery):
    remember_user(callback.from_user)
    await callback.answer()
    if not PRODUCTS:
        await callback.message.answer(
            "🛒 Hozircha do'konda mahsulot yo'q. Tez orada yangi materiallar qo'shiladi!"
        )
        return
    await callback.message.answer(
        "🛒 <b>Mavjud materiallar:</b>\nSotib olish uchun mahsulotni tanlang.",
        parse_mode="HTML",
        reply_markup=build_shop_keyboard(),
    )


@dp.callback_query(F.data == "shop_close")
async def shop_close(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@dp.callback_query(F.data.startswith("buy:"))
async def shop_buy(callback: CallbackQuery):
    product_id = callback.data.split(":", 1)[1]
    product = PRODUCTS.get(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi.", show_alert=True)
        return
    await callback.answer()

    if product.get("payment_method") == "card":
        pending_card_orders[callback.from_user.id] = product_id
        await callback.message.answer(
            f"🛒 <b>{product['title']}</b>\n"
            f"Narxi: <b>{product.get('price_display', '—')}</b>\n\n"
            f"To'lov uchun quyidagi kartaga o'tkazma qiling:\n"
            f"💳 <code>{DONATE_CARD_NUMBER}</code>\n"
            f"{DONATE_CARD_HOLDER}\n\n"
            f"To'lovni amalga oshirgach, chekning (yoki ilova ekranining) "
            f"<b>skrinshotini shu yerga rasm sifatida yuboring</b>. "
            f"Men tekshirib, tasdiqlagach, fayl avtomatik yuboriladi.",
            parse_mode="HTML",
        )
        return

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=product["title"],
        description=product["description"],
        payload=f"buy_{product_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=product["title"], amount=product["price_stars"])],
    )


@dp.message(F.photo)
async def handle_payment_proof(message: Message):
    user_id = message.from_user.id
    product_id = pending_card_orders.get(user_id)
    if not product_id:
        return  # Bu foydalanuvchidan kutilayotgan to'lov yo'q — e'tiborsiz qoldiramiz

    product = PRODUCTS.get(product_id)
    if not product:
        pending_card_orders.pop(user_id, None)
        await message.answer("Xatolik: mahsulot topilmadi. Iltimos, qaytadan urinib ko'ring.")
        return

    name = remember_user(message.from_user)
    username_part = f"@{message.from_user.username}" if message.from_user.username else "(username yo'q)"

    await bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=message.photo[-1].file_id,
        caption=(
            f"🛒 Yangi to'lov cheki\n"
            f"Foydalanuvchi: {name} {username_part} (ID: {user_id})\n"
            f"Mahsulot: {product['title']}\n"
            f"Narxi: {product.get('price_display', '—')}"
        ),
        reply_markup=build_admin_approval_kb(user_id, product_id),
    )
    await message.answer(
        "✅ Skrinshot qabul qilindi va tekshirish uchun yuborildi. "
        "Tasdiqlangach, fayl avtomatik yuboriladi. Iltimos kuting."
    )


@dp.callback_query(F.data.startswith("approve_order:"))
async def approve_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    _, user_id_str, product_id = callback.data.split(":", 2)
    user_id = int(user_id_str)
    product = PRODUCTS.get(product_id)

    if not product:
        await callback.answer("Mahsulot topilmadi.", show_alert=True)
        return

    file_path = get_material_path(product["filename"])
    if not os.path.exists(file_path):
        await callback.answer("Fayl serverda topilmadi!", show_alert=True)
        return

    await bot.send_message(user_id, f"✅ To'lovingiz tasdiqlandi! \"{product['title']}\" fayli yuborilmoqda...")
    await bot.send_document(user_id, FSInputFile(file_path))
    pending_card_orders.pop(user_id, None)

    await callback.answer("Tasdiqlandi va fayl yuborildi ✅")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ TASDIQLANDI")


@dp.callback_query(F.data.startswith("reject_order:"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    _, user_id_str, product_id = callback.data.split(":", 2)
    user_id = int(user_id_str)

    await bot.send_message(
        user_id,
        "❌ To'lovingiz tasdiqlanmadi. Agar bu xato deb hisoblasangiz, "
        "administrator bilan bog'laning yoki qaytadan urinib ko'ring."
    )
    pending_card_orders.pop(user_id, None)

    await callback.answer("Rad etildi")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ RAD ETILDI")


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    name = remember_user(message.from_user)
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount

    if payload.startswith("buy_"):
        product_id = payload[len("buy_"):]
        product = PRODUCTS.get(product_id)
        if not product:
            await message.answer(
                f"✅ To'lov qabul qilindi, lekin mahsulot topilmadi. "
                f"Iltimos, administratorga murojaat qiling (ID: {product_id})."
            )
            return
        file_path = get_material_path(product["filename"])
        if not os.path.exists(file_path):
            await message.answer(
                "✅ To'lovingiz qabul qilindi! Fayl hozircha serverga yuklanmagan — "
                "tez orada yuboriladi, iltimos kuting yoki administratorga murojaat qiling."
            )
            return
        await message.answer(f"✅ Rahmat, {name}! To'lovingiz ({stars} ⭐) qabul qilindi. Fayl yuborilmoqda...")
        await bot.send_document(message.chat.id, FSInputFile(file_path))
    else:
        await message.answer(
            f"✅ Rahmat, {name}! {stars} ⭐ Stars uchun donatingiz qabul qilindi. Sizga minnatdormiz! ❤️"
        )


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = remember_user(message.from_user)
    await message.answer(
        f"Assalomu alaykum, {name}! 👋\n\n"
        "Bu bot <b>Multilevel CEFR Writing</b> vazifalarini baholaydi.\n"
        "Vazifani <b>saytda</b> (audio/fayl yuklash imkoni bilan) yoki "
        "bevosita <b>shu yerda, botda</b> matn yuborib bajarishingiz mumkin:\n\n"
        f"• <b>Task 1.1</b> — norasmiy email ({TASKS['1.1']['word_range']}, maqsad daraja B1)\n"
        f"• <b>Task 1.2</b> — rasmiy email ({TASKS['1.2']['word_range']}, maqsad daraja B2)\n"
        f"• <b>Task 2</b> — blog/forum posti ({TASKS['2']['word_range']}, maqsad daraja C1)\n\n"
        "Botni yoqtirsangiz, /donate orqali qo'llab-quvvatlashingiz mumkin 🙏",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


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
        task_prompt = await generate_task_prompt(task_key, user_key=callback.from_user.id)
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


ERROR_TYPE_LABELS = {
    "grammar": "📐 Grammatik xatolar",
    "spelling": "🔤 Imloviy xatolar",
    "run_on": "➰ Run-on gaplar / tinish belgilari",
    "register": "🎭 Uslub (formal/informal) xatolari",
}
ERROR_TYPE_ORDER = ["grammar", "spelling", "run_on", "register"]


def format_errors_section(errors: list) -> str:
    """Baholash natijasidagi 'errors' ro'yxatini turkumlarga ajratib,
    o'qish uchun qulay HTML matniga aylantiradi. Xato bo'lmasa bo'sh
    satr qaytaradi."""
    if not errors:
        return ""
    by_type: dict[str, list] = {}
    for err in errors:
        by_type.setdefault(err.get("type"), []).append(err)

    blocks = []
    for err_type in ERROR_TYPE_ORDER:
        items = by_type.get(err_type)
        if not items:
            continue
        lines = [f"<b>{ERROR_TYPE_LABELS[err_type]}:</b>"]
        for e in items:
            original = html.escape(e.get("original", ""))
            correction = html.escape(e.get("correction", ""))
            explanation = html.escape(e.get("explanation", ""))
            if correction:
                lines.append(f"  • <s>{original}</s> → <b>{correction}</b>")
            else:
                lines.append(f"  • {original}")
            if explanation:
                lines.append(f"    <i>{explanation}</i>")
        blocks.append("\n".join(lines))

    if not blocks:
        return ""
    return "\n\n<u>Aniqlangan xatolar:</u>\n" + "\n\n".join(blocks) + "\n"


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
        try:
            await db.save_pending_submission(
                user_id=user_id, task_key=task_key, text=text, task_prompt=task_prompt,
                timed=timed_info.get("timed", False),
                start_time=timed_info.get("start_time"),
                time_limit=timed_info.get("time_limit"),
            )
        except Exception:
            logger.exception("Pending submission'ni bazaga saqlashda xatolik")
        await status_message.edit_text(
            f"⚠️ {name}, baholashda texnik xatolik yuz berdi: {last_error}\n"
            "Bu odatda vaqtinchalik holat (server band). Quyidagi tugma orqali qayta urinib ko'ring.",
            reply_markup=retry_kb(),
        )
        return

    try:
        await db.delete_pending_submission(user_id)
    except Exception:
        logger.exception("Pending submission'ni bazadan o'chirishda xatolik")
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
    errors_section = format_errors_section(result.get("errors", []))

    time_line = ""
    if timed_info.get("timed") and timed_info.get("start_time"):
        start_time = datetime.fromisoformat(timed_info["start_time"])
        elapsed = (datetime.now() - start_time).total_seconds()
        limit_sec = timed_info["time_limit"] * 60
        status = "✅ Vaqtida yakunladingiz" if elapsed <= limit_sec else f"⚠️ Vaqtdan {format_elapsed(elapsed - limit_sec)} ga oshirib yubordingiz"
        time_line = f"⏱️ Sarflangan vaqt: <b>{format_elapsed(elapsed)}</b> (chegarasi {timed_info['time_limit']} daq) — {status}\n"

    header = (
        f"📝 <b>{task['title']}</b>\n"
        f"{name}, ballingiz: <b>{result['score']}/{task['max_score']}</b>\n"
        f"Taxminiy daraja: <b>{result.get('estimated_cefr_level', '—')}</b>\n"
        f"{time_line}"
        f"So'zlar soni: {result.get('word_count_comment', '—')}\n\n"
        f"<u>Kuchli tomonlari:</u>\n{strengths}\n\n"
        f"<u>Yaxshilash kerak:</u>\n{improvements}\n"
    )
    footer = f"\n💬 {result.get('comment', '')}"

    # Telegram xabar uzunligi chegarasi (4096) tufayli, agar xatolar bo'limi
    # bilan birga umumiy matn juda uzun bo'lib qolsa, uni alohida xabarga
    # ajratamiz — shunda hech qanday ma'lumot kesilib qolmaydi.
    full_text = header + errors_section + footer
    if len(full_text) <= 4000:
        await status_message.edit_text(full_text, parse_mode="HTML")
    else:
        await status_message.edit_text(header + footer, parse_mode="HTML")
        if errors_section:
            for chunk_start in range(0, len(errors_section), 3800):
                chunk = errors_section[chunk_start:chunk_start + 3800]
                await bot.send_message(chat_id, chunk, parse_mode="HTML")

    await send_results(chat_id, user_id)

    # Kanalga taklif — spam bo'lib qolmasligi uchun har safar emas,
    # tasodifiy ~30% ehtimol bilan ko'rsatiladi
    if CHANNEL_ID:
        if random.random() < 0.3:
            channel_username = CHANNEL_ID.lstrip("@")
            channel_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=f"https://t.me/{channel_username}")
            ]])
            await bot.send_message(
                chat_id,
                "💡 Har kuni idiom, phrasal verb va foydali materiallar uchun "
                "kanalimizga qo'shiling!",
                reply_markup=channel_kb,
            )


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
    try:
        pending = await db.get_pending_submission(callback.from_user.id)
    except Exception:
        logger.exception("Pending submission'ni bazadan o'qishda xatolik")
        pending = None
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


@dp.message()
async def fallback(message: Message):
    name = remember_user(message.from_user)
    await message.answer(f"{name}, vazifani tanlash uchun /start buyrug'ini yuboring.", reply_markup=main_menu_kb())


async def main():
    await db.init_db()
    logger.info("Baza tayyor")

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
