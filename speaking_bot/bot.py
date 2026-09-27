"""
CEFR Multilevel Speaking imtihonini baholovchi Telegram bot.

Ishlash tartibi:
1. Foydalanuvchi tugmalar orqali imtihon qismini tanlaydi:
   Part 1.1 / Part 1.2 / Part 2 / Part 3.
2. Foydalanuvchi shu qism uchun savol(lar)ni matn yoki rasm ko'rinishida
   yuboradi (rasmdagi matn Groq'ning vizual modeli orqali o'qiladi).
3. Foydalanuvchi savolga bitta yoki bir nechta ovozli xabar bilan javob
   beradi.
4. "✅ Yakunlash" tugmasi bosilganda barcha xabarlar Whisper API orqali
   matnga aylantiriladi va audio signallari (pauza, tezlik, akustik
   ishonch) hisoblanadi.
5. Yig'ilgan transkript, savol matni va audio signallari birgalikda,
   TANLANGAN QISMGA mos rasmiy rubrika bilan Groq'ning til modeliga
   yuboriladi.
6. Foydalanuvchiga tayyor baholash hisoboti qaytariladi.

Bundan tashqari, bot bilan bir qatorda kichik "hayotdalik" (health-check)
veb-server ham ishga tushiriladi (aiohttp orqali). Bu Render.com kabi
"Web Service" turidagi bepul xosting xizmatlarida ishlatish uchun kerak —
ular dastur biror portni tinglashini talab qiladi. Tashqi "uptime ping"
xizmati (masalan UptimeRobot) shu portga muntazam so'rov yuborib, servisni
"uxlab qolishdan" saqlaydi.

Ishga tushirish:
    pip install -r requirements.txt
    .env faylini to'ldiring (TELEGRAM_BOT_TOKEN, GROQ_API_KEY)
    python bot.py
"""
import asyncio
import logging
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    LabeledPrice,
    PreCheckoutQuery,
    FSInputFile,
)

from config import TELEGRAM_BOT_TOKEN, CHANNEL_ID
from transcriber import transcribe_audio
from evaluator import evaluate_transcript
from vision import extract_question_from_image, describe_image_url
from rubric import PART_LABELS, get_rubric
from question_bank import get_random_question
from picture_bank import get_random_picture_pair, get_random_morning_photo
from overall_score import compute_overall, MAX_RAW_SCORES
from products import PRODUCTS, build_shop_keyboard, build_admin_approval_kb, get_material_path
import channel_content
import speaking_db as sdb
import achievements as ach

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Render (va shunga o'xshash xizmatlar) PORT o'zgaruvchisini avtomatik beradi.
# Lokal kompyuterda ishga tushirganda bu o'zgaruvchi bo'lmaydi, shuning uchun
# standart qiymat sifatida 8080 ishlatiladi.
PORT = int(os.getenv("PORT", "8080"))

# --- Sayt manzili (Telegram Mini App / Web App tugmasi uchun) ---
# ?tab=speaking qismi sayt ochilganda avtomatik Speaking bo'limini ko'rsatadi.
SPEAKING_SITE_URL = os.getenv(
    "SPEAKING_SITE_URL",
    "https://cefr-multilevel-test-speaking-writing.netlify.app/?tab=speaking",
)

# --- Do'kon: admin ID (karta orqali to'lovlarni tasdiqlash uchun) ---
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "817610690"))

# Karta orqali to'lov kutilayotgan buyurtmalar: {user_id: product_id}
pending_card_orders: dict[int, str] = {}

# Xayriya (donat) kartasi. Karta raqami monospace (`...`) formatida yozilgan —
# Telegram mobil ilovasida bunday matnga bosilganda avtomatik nusxalanadi.
DONATE_CARD_NUMBER = "8600 0609 4603 0849"
DONATE_CARD_HOLDER = "J.Ergashev"
DONATE_TEXT = (
    "💳 *Botni qo'llab-quvvatlash*\n\n"
    "Agar bot foydali bo'lgan bo'lsa, xohishga ko'ra quyidagi UzCard "
    "kartasiga xayriya qilishingiz mumkin:\n\n"
    f"`{DONATE_CARD_NUMBER}`\n"
    f"{DONATE_CARD_HOLDER}\n\n"
    "_(Karta raqamiga bosib, uni nusxalab olishingiz mumkin)_\n\n"
    "Rahmat! 🙏"
)
DONATE_BUTTON = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="💳 Donate", callback_data="donate")]]
)

PART_SELECT_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Part 1.1 (A1/A2)", callback_data="part:1.1")],
        [InlineKeyboardButton(text="Part 1.2 (A2/B1)", callback_data="part:1.2")],
        [InlineKeyboardButton(text="Part 2 (B1/B2)", callback_data="part:2")],
        [InlineKeyboardButton(text="Part 3 (B2/C1)", callback_data="part:3")],
    ]
)

def _part_action_kb(part: str) -> InlineKeyboardMarkup:
    """Qism tanlangandan keyin ko'rsatiladigan: tasodifiy savol tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Tasodifiy savol bering", callback_data=f"randomq:{part}")]
        ]
    )


MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌐 Saytda test topshirish")],
        [KeyboardButton(text="📚 Qism tanlash")],
        [KeyboardButton(text="✅ Yakunlash va baholash")],
        [KeyboardButton(text="📈 Mening natijalarim"), KeyboardButton(text="🏆 Yutuqlarim")],
        [KeyboardButton(text="📊 Umumiy ball (75)"), KeyboardButton(text="🔥 Reyting")],
        [KeyboardButton(text="🤝 Do'st taklif qilish")],
        [KeyboardButton(text="🛒 Materiallar do'koni")],
        [KeyboardButton(text="🔄 Bekor qilish"), KeyboardButton(text="💳 Donate")],
    ],
    resize_keyboard=True,
)


@dataclass
class UserSession:
    part: str | None = None  # "1.1" | "1.2" | "2" | "3"
    question_text: str = ""
    awaiting_question: bool = False
    audio_files: list = field(default_factory=list)


# Har bir foydalanuvchi uchun joriy sessiya (RAMda saqlanadi)
user_sessions: dict[int, UserSession] = defaultdict(UserSession)

# Har bir foydalanuvchi uchun o'tgan natijalar tarixi (RAMda saqlanadi;
# bot qayta ishga tushirilsa tozalanadi). Har element: dict(part, score_line, when)
user_history: dict[int, list] = defaultdict(list)
MAX_HISTORY_PER_USER = 20


# ---------------------------------------------------------------------------
# YUTUQLAR (achievements) — berish va tabriklash
# ---------------------------------------------------------------------------
async def _grant_and_notify(user_id: int, key: str, user_name: str):
    """Yutuqni beradi va agar u YANGI bo'lsa, foydalanuvchini tabriklaydi."""
    try:
        is_new = await sdb.grant_achievement(user_id, key)
        if is_new:
            text = ach.format_achievement_message(key, user_name)
            if text:
                await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception:
        logger.exception(f"Yutuq berishda xatolik: {key}")


async def _check_referral_achievements(user_id: int, count: int):
    user = await sdb.get_user(user_id)
    name = (user or {}).get("user_name") or "Foydalanuvchi"
    if count >= 20:
        await _grant_and_notify(user_id, "referral_20", name)
    elif count >= 5:
        await _grant_and_notify(user_id, "referral_5", name)
    elif count >= 1:
        await _grant_and_notify(user_id, "referral_1", name)


async def _check_streak_achievements(user_id: int, streak: int, name: str):
    if streak >= 30:
        await _grant_and_notify(user_id, "streak_30", name)
    elif streak >= 7:
        await _grant_and_notify(user_id, "streak_7", name)
    elif streak >= 3:
        await _grant_and_notify(user_id, "streak_3", name)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_sessions[message.from_user.id] = UserSession()

    # Referal havolasini o'qiymiz: /start ref_123456789
    referred_by = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            referred_by = int(parts[1][4:])
        except ValueError:
            referred_by = None

    user = message.from_user
    display_name = user.first_name or user.username or "Foydalanuvchi"
    try:
        result = await sdb.register_user(user.id, display_name, user.username, referred_by)
        if result["referral_applied"] and referred_by:
            # Taklif qiluvchiga xabar beramiz va yutuqlarini tekshiramiz
            try:
                stats = await sdb.get_referral_stats(referred_by)
                await bot.send_message(
                    referred_by,
                    f"🎉 <b>{display_name}</b> sizning havolangiz orqali botga qo'shildi!\n"
                    f"Jami taklif qilganlaringiz: <b>{stats['count']}</b> kishi.",
                    parse_mode="HTML",
                )
                await _check_referral_achievements(referred_by, stats["count"])
            except Exception:
                logger.exception("Taklif qiluvchiga xabar yuborishda xatolik")
    except Exception:
        logger.exception("Foydalanuvchini bazaga yozishda xatolik")

    await message.answer(
        "Assalomu alaykum! Men CEFR Multilevel imtihonining "
        "*Gapirish (Speaking)* qismini baholovchi botman.\n\n"
        "Vazifani *saytda* (rasm/audio faylni oson yuklash imkoni bilan) "
        "yoki bevosita *shu yerda, botda* bajarishingiz mumkin.\n\n"
        "📋 *Botda qanday ishlaydi:*\n"
        "1. *\"📚 Qism tanlash\"* orqali imtihon qismini tanlang "
        "(Part 1.1 / 1.2 / 2 / 3).\n"
        "2. Shu qism uchun savolni matn yoki rasm ko'rinishida yuboring.\n"
        "3. Savolga ovozli xabar (voice message) bilan javob bering. "
        "Bir nechta xabar yuborishingiz mumkin.\n"
        "4. Javoblaringizni tugatgach, *\"✅ Yakunlash va baholash\"* "
        "tugmasini bosing.\n"
        "5. Men javoblaringizni matnga aylantirib, tanlangan qismga mos "
        "rasmiy rubrika asosida baholayman.\n\n"
        "Boshlash uchun *\"📚 Qism tanlash\"* yoki *\"🌐 Saytda test topshirish\"* "
        "tugmasini bosing 👇\n\n"
        "_Bot foydali bo'lsa, /donate orqali qo'llab-quvvatlashingiz mumkin._",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )


@dp.message(Command("qism"))
@dp.message(F.text == "📚 Qism tanlash")
async def cmd_choose_part(message: Message):
    await message.answer(
        "Qaysi qism uchun mashq qilmoqchisiz?", reply_markup=PART_SELECT_KB
    )


# ---------------------------------------------------------------------------
# REFERAL — do'st taklif qilish
# ---------------------------------------------------------------------------
@dp.message(Command("referal"))
@dp.message(F.text == "🤝 Do'st taklif qilish")
async def cmd_referral(message: Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    try:
        stats = await sdb.get_referral_stats(user_id)
        count = stats["count"]
    except Exception:
        logger.exception("Referal statistikasini olishda xatolik")
        count = 0

    share_text = (
        "CEFR Multilevel Speaking imtihoniga bepul tayyorlanaman — "
        "bot ovozimni baholab, aniq fikr-mulohaza beradi. Sen ham sinab ko'r!"
    )
    share_url = f"https://t.me/share/url?url={link}&text={share_text}"

    share_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url)
    ]])

    await message.answer(
        f"🤝 <b>Do'st taklif qiling</b>\n\n"
        f"Quyidagi shaxsiy havolangizni do'stlaringizga yuboring. "
        f"Ular shu havola orqali botga qo'shilsa, sizning hisobingizga yoziladi "
        f"va maxsus yutuqlarni qo'lga kiritasiz.\n\n"
        f"🔗 Havolangiz:\n<code>{link}</code>\n\n"
        f"👥 Hozirgacha taklif qilganlaringiz: <b>{count}</b> kishi\n\n"
        f"<i>Yutuqlar: 1 ta do'st 🤝 | 5 ta do'st 🌟 | 20 ta do'st 👑</i>",
        parse_mode="HTML",
        reply_markup=share_kb,
    )


# ---------------------------------------------------------------------------
# YUTUQLAR — sertifikat ko'rinishida
# ---------------------------------------------------------------------------
@dp.message(Command("yutuqlar"))
@dp.message(F.text == "🏆 Yutuqlarim")
async def cmd_achievements(message: Message):
    user_id = message.from_user.id
    name = message.from_user.first_name or "Foydalanuvchi"

    try:
        user = await sdb.get_user(user_id)
        my_achievements = await sdb.get_achievements(user_id)
        streak = (user or {}).get("current_streak", 0) or 0
        referrals = (user or {}).get("referral_count", 0) or 0
    except Exception:
        logger.exception("Yutuqlarni olishda xatolik")
        await message.answer("Yutuqlarni yuklashda texnik xatolik yuz berdi.")
        return

    certificate = ach.format_certificate(name, my_achievements, streak, referrals)

    share_url = f"https://t.me/share/url?url=https://t.me/{(await bot.get_me()).username}&text={certificate}"
    share_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📤 Natijalarimni ulashish", url=share_url)
    ]])

    await message.answer(certificate, parse_mode="HTML", reply_markup=share_kb)


# ---------------------------------------------------------------------------
# REYTING — haftalik, streak va referal bo'yicha
# ---------------------------------------------------------------------------
@dp.message(Command("reyting"))
@dp.message(F.text == "🔥 Reyting")
async def cmd_leaderboard(message: Message):
    try:
        weekly = await sdb.get_weekly_leaderboard(10)
        streaks = await sdb.get_streak_leaderboard(5)
        referrals = await sdb.get_referral_leaderboard(5)
    except Exception:
        logger.exception("Reytingni olishda xatolik")
        await message.answer("Reytingni yuklashda texnik xatolik yuz berdi.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>REYTING</b>\n"]

    lines.append("<b>📊 Bu haftaning eng yaxshi natijalari</b>")
    if weekly:
        for i, row in enumerate(weekly):
            prefix = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{prefix} {row['user_name']} — {row['avg_percent']}% ({row['attempts']} urinish)")
    else:
        lines.append("<i>Bu hafta hali natijalar yo'q — birinchi bo'ling!</i>")

    lines.append("\n<b>🔥 Eng uzun streak</b>")
    if streaks:
        for i, row in enumerate(streaks):
            prefix = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{prefix} {row['user_name']} — {row['current_streak']} kun")
    else:
        lines.append("<i>Hali streak egalari yo'q.</i>")

    lines.append("\n<b>🤝 Eng ko'p do'st taklif qilganlar</b>")
    if referrals:
        for i, row in enumerate(referrals):
            prefix = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{prefix} {row['user_name']} — {row['referral_count']} kishi")
    else:
        lines.append("<i>Hali taklif qilganlar yo'q.</i>")

    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(F.text == "🌐 Saytda test topshirish")
async def cmd_open_site(message: Message):
    site_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🌐 Saytni ochish", url=SPEAKING_SITE_URL)]]
    )
    await message.answer(
        "Saytda test topshirish uchun quyidagi tugmani bosing 👇\n"
        "(Sayt tashqi brauzerda ochiladi)",
        reply_markup=site_kb,
    )


# ---------------------------------------------------------------------------
# DO'KON: materiallar (handout/worksheet) sotish — Telegram Stars orqali
# ---------------------------------------------------------------------------
@dp.message(F.text == "🛒 Materiallar do'koni")
async def cmd_shop(message: Message):
    if not PRODUCTS:
        await message.answer(
            "🛒 Hozircha do'konda mahsulot yo'q. Tez orada yangi materiallar qo'shiladi!"
        )
        return
    await message.answer(
        "🛒 Mavjud materiallar:\nSotib olish uchun mahsulotni tanlang.",
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
            f"🛒 *{product['title']}*\n"
            f"Narxi: *{product.get('price_display', '—')}*\n\n"
            f"To'lov uchun quyidagi kartaga o'tkazma qiling:\n"
            f"💳 `{DONATE_CARD_NUMBER}`\n"
            f"{DONATE_CARD_HOLDER}\n\n"
            f"To'lovni amalga oshirgach, chekning skrinshotini shu yerga "
            f"rasm sifatida yuboring. Tekshirilgach, fayl avtomatik yuboriladi.",
            parse_mode="Markdown",
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
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount

    if not payload.startswith("buy_"):
        return

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
            "tez orada yuboriladi, iltimos administratorga murojaat qiling."
        )
        return

    await message.answer(f"✅ Rahmat! To'lovingiz ({stars} ⭐) qabul qilindi. Fayl yuborilmoqda...")
    await bot.send_document(message.chat.id, FSInputFile(file_path))


@dp.callback_query(F.data.startswith("part:"))
async def callback_choose_part(callback: CallbackQuery):
    part = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    session = user_sessions[user_id]
    session.part = part
    session.question_text = ""
    session.awaiting_question = True
    _cleanup_files(user_id)
    session.audio_files = []

    await callback.message.answer(
        f"✅ Tanlandi: {PART_LABELS[part]}\n\n"
        "Endi shu qism uchun savolni yuboring — matn ko'rinishida yozib "
        "yoki rasm (screenshot) tariqasida joylab yuborishingiz mumkin. "
        "Yoki pastdagi tugma orqali tasodifiy savol oling.",
        reply_markup=MAIN_KB,
    )
    await callback.message.answer(
        "🎲 Yoki tasodifiy savol olish uchun bosing:",
        reply_markup=_part_action_kb(part),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("randomq:"))
async def callback_random_question(callback: CallbackQuery):
    part = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    session = user_sessions[user_id]

    if session.part != part:
        # Ehtimol foydalanuvchi keyinroq bosgan, qismni qayta tiklaymiz
        session.part = part

    if part == "1.2":
        await _send_random_picture_pair(callback.message, session)
        await callback.answer()
        return

    question = get_random_question(part)
    session.question_text = question
    session.awaiting_question = False

    await callback.message.answer(f"🎲 Sizning savolingiz:\n\n{question}")
    await callback.message.answer(
        "Endi shu savolga ovozli xabar bilan javob bering 🎙",
        reply_markup=MAIN_KB,
    )
    await callback.answer()


async def _send_random_picture_pair(message: Message, session: "UserSession"):
    """Part 1.2 uchun Unsplash'dan tasodifiy surat juftini oladi, ikkala
    suratni foydalanuvchiga yuboradi, va ularning tavsifini + 3 ta savolni
    baholash konteksti sifatida sessiyaga saqlaydi."""
    status_msg = await message.answer("⏳ Tasodifiy suratlar olinmoqda...")
    try:
        pair = await get_random_picture_pair()

        await bot.send_photo(message.chat.id, photo=pair["image1_url"])
        await bot.send_photo(message.chat.id, photo=pair["image2_url"])

        desc1 = await describe_image_url(pair["image1_url"])
        desc2 = await describe_image_url(pair["image2_url"])

        questions_text = "\n".join(pair["questions"])
        session.question_text = (
            f"SAVOLLAR:\n{questions_text}\n\n"
            f"RASMLARDAGI TASVIR:\n1-rasm: {desc1}\n2-rasm: {desc2}"
        )
        session.awaiting_question = False

        await status_msg.delete()
        await message.answer(f"❓ Savollar:\n\n{questions_text}")
        await message.answer(
            "Yuqoridagi ikkita suratni tasvirlab, savollarga ovozli javob bering 🎙",
            reply_markup=MAIN_KB,
        )
    except Exception as e:
        logger.exception("Tasodifiy surat juftini olishda xatolik")
        await status_msg.edit_text(
            f"❌ Suratlarni olishda xatolik yuz berdi: {e}\n\n"
            "Buning o'rniga o'zingiz rasm yuklashingiz mumkin."
        )


@dp.message(Command("bekor"))
@dp.message(F.text == "🔄 Bekor qilish")
async def cmd_cancel(message: Message):
    _cleanup_files(message.from_user.id)
    user_sessions[message.from_user.id] = UserSession()
    await message.answer("Sessiya tozalandi. \"📚 Qism tanlash\" orqali qaytadan boshlashingiz mumkin.")


@dp.message(Command("donate"))
@dp.message(F.text == "💳 Donate")
async def cmd_donate(message: Message):
    await message.answer(DONATE_TEXT, parse_mode="Markdown")


@dp.callback_query(F.data == "donate")
async def callback_donate(callback: CallbackQuery):
    await callback.message.answer(DONATE_TEXT, parse_mode="Markdown")
    await callback.answer()


def _has_pending_card_order(message: Message) -> bool:
    return message.from_user.id in pending_card_orders


@dp.message(F.photo, _has_pending_card_order)
async def handle_payment_proof(message: Message):
    """Agar foydalanuvchi karta orqali to'lov kutayotgan bo'lsa, yuborilgan
    rasm imtihon savoli emas, balki to'lov cheki deb hisoblanadi va
    adminga tekshirish uchun yuboriladi. Bu handler pastdagi umumiy
    handle_photo (imtihon savoli uchun) dan OLDIN ro'yxatdan o'tgani
    uchun, faqat pending buyurtma bo'lgandagina ishlaydi."""
    user_id = message.from_user.id
    product_id = pending_card_orders.get(user_id)
    product = PRODUCTS.get(product_id)
    if not product:
        pending_card_orders.pop(user_id, None)
        await message.answer("Xatolik: mahsulot topilmadi. Iltimos, qaytadan urinib ko'ring.")
        return

    username_part = f"@{message.from_user.username}" if message.from_user.username else "(username yo'q)"

    await bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=message.photo[-1].file_id,
        caption=(
            f"🛒 Yangi to'lov cheki\n"
            f"Foydalanuvchi: {username_part} (ID: {user_id})\n"
            f"Mahsulot: {product['title']}\n"
            f"Narxi: {product.get('price_display', '—')}"
        ),
        reply_markup=build_admin_approval_kb(user_id, product_id),
    )
    await message.answer(
        "✅ Skrinshot qabul qilindi va tekshirish uchun yuborildi. "
        "Tasdiqlangach, fayl avtomatik yuboriladi. Iltimos kuting."
    )


@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    session = user_sessions[user_id]

    if session.part is None:
        await message.answer(
            "Avval \"📚 Qism tanlash\" orqali imtihon qismini tanlang, "
            "keyin savolni rasm sifatida yuboring."
        )
        return

    status_msg = await message.answer("⏳ Rasm o'qilmoqda...")

    try:
        # Eng katta o'lchamdagi versiyasini olamiz (Telegram bir nechta o'lcham yuboradi)
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        tmp_dir = tempfile.gettempdir()
        local_path = os.path.join(tmp_dir, f"{user_id}_{photo.file_id}.jpg")
        await bot.download_file(file.file_path, destination=local_path)

        extracted = await extract_question_from_image(local_path)
        os.remove(local_path)

        # Bir nechta rasm ketma-ket yuborilishi mumkin (masalan 2 ta alohida
        # surat) — shuning uchun mavjud savol matniga qo'shib boramiz,
        # darhol yakunlamaymiz.
        if session.question_text:
            session.question_text += f"\n\n--- (yana bir rasm) ---\n{extracted}"
        else:
            session.question_text = extracted
        session.awaiting_question = True  # yana rasm/matn qo'shish imkoni qoladi

        await status_msg.edit_text("✅ Rasmdan o'qildi:")
        await safe_send(message, extracted)
        await message.answer(
            "Agar yana rasm yoki matn qo'shmoqchi bo'lsangiz, yuborishda "
            "davom eting. Tayyor bo'lsa, pastdagi tugmani bosing yoki "
            "to'g'ridan-to'g'ri ovozli javob yuboring.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Savol(lar) tayyor", callback_data="question_done")]
                ]
            ),
        )
    except Exception as e:
        logger.exception("Rasmni o'qishda xatolik")
        await status_msg.edit_text(f"❌ Rasmni o'qishda xatolik yuz berdi: {e}")


@dp.callback_query(F.data == "question_done")
async def callback_question_done(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions[user_id]
    session.awaiting_question = False
    await callback.message.answer(
        "Endi savol(lar)ga ovozli xabar bilan javob bering 🎙", reply_markup=MAIN_KB
    )
    await callback.answer()


@dp.message(F.voice | F.audio)
async def handle_voice(message: Message):
    user_id = message.from_user.id
    session = user_sessions[user_id]

    if session.part is None:
        await message.answer(
            "Avval \"📚 Qism tanlash\" orqali imtihon qismini va savolni tanlang."
        )
        return

    if session.awaiting_question and not session.question_text:
        await message.answer(
            "Avval savolni (matn yoki rasm) yuboring, keyin ovozli javob bering."
        )
        return

    # Agar savol(lar) allaqachon kiritilgan bo'lsa-yu, foydalanuvchi
    # to'g'ridan-to'g'ri ovozli xabar yuborsa — bu "savol tayyor" degani,
    # avtomatik yakunlaymiz (qo'shimcha tugma bosishga majburlamaymiz).
    session.awaiting_question = False

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)

    tmp_dir = tempfile.gettempdir()
    local_path = os.path.join(tmp_dir, f"{user_id}_{file_id}.ogg")
    await bot.download_file(file.file_path, destination=local_path)

    session.audio_files.append(local_path)
    count = len(session.audio_files)

    await message.answer(
        f"🎙 Ovozli xabar qabul qilindi ({count}-ta). "
        f"Yana yuborishingiz mumkin yoki \"✅ Yakunlash va baholash\" tugmasini bosing.",
        reply_markup=MAIN_KB,
    )


@dp.message(F.text == "✅ Yakunlash va baholash")
async def handle_finish(message: Message):
    user_id = message.from_user.id
    session = user_sessions[user_id]

    if session.part is None:
        await message.answer(
            "Avval \"📚 Qism tanlash\" orqali imtihon qismini tanlang."
        )
        return

    files = session.audio_files
    if not files:
        await message.answer(
            "Hali hech qanday ovozli xabar yubormadingiz. "
            "Iltimos, avval savolga ovozli javob bering 🎙"
        )
        return

    status_msg = await message.answer("⏳ Audio matnga aylantirilmoqda...")

    try:
        transcripts = []
        all_metrics = []
        for idx, path in enumerate(files, start=1):
            metrics = await transcribe_audio(path, language="en")
            transcripts.append(f"[{idx}-javob]: {metrics.text}")
            all_metrics.append(metrics)

        full_transcript = "\n\n".join(transcripts)

        # Barcha javoblar bo'yicha audio signallarini birlashtirib, o'rtacha/yig'indi hisoblaymiz
        total_duration = sum(m.duration_sec for m in all_metrics)
        total_pauses = sum(m.pause_count for m in all_metrics)
        total_pause_sec = sum(m.total_pause_sec for m in all_metrics)
        longest_pause = max((m.longest_pause_sec for m in all_metrics), default=0.0)
        total_fillers = sum(m.filler_count for m in all_metrics)
        avg_wpm = (
            sum(m.speaking_words_per_min for m in all_metrics) / len(all_metrics)
            if all_metrics
            else 0.0
        )
        avg_logprob = (
            sum(m.avg_logprob for m in all_metrics) / len(all_metrics) if all_metrics else 0.0
        )
        avg_no_speech = (
            sum(m.avg_no_speech_prob for m in all_metrics) / len(all_metrics)
            if all_metrics
            else 0.0
        )
        total_low_confidence = sum(m.low_confidence_segment_count for m in all_metrics)

        audio_summary = (
            f"- Umumiy audio davomiyligi (barcha javoblar): {total_duration:.1f} soniya\n"
            f"- O'rtacha gapirish tezligi: {avg_wpm:.0f} so'z/daqiqa\n"
            f"- Pauzalar (0.5s+): {total_pauses} ta, jami {total_pause_sec:.1f}s, "
            f"eng uzuni {longest_pause:.1f}s\n"
            f"- Filler/ikkilanish so'zlari: {total_fillers} marta\n"
            f"- Whisper akustik ishonch darajasi (avg_logprob): {avg_logprob:.2f} "
            f"(0 ga yaqin = aniq eshitilgan, -1 dan past = noaniq/tushunarsiz)\n"
            f"- Nutqsiz/noaniq segmentlar ulushi: {avg_no_speech*100:.0f}%\n"
            f"- Past ishonchli (ehtimol noaniq talaffuzli) segmentlar soni: {total_low_confidence}"
        )

        await status_msg.edit_text("⏳ CEFR mezoni asosida baholanmoqda...")

        rubric_text = get_rubric(session.part)
        report = await evaluate_transcript(
            full_transcript,
            rubric_text,
            questions=session.question_text,
            audio_metrics_summary=audio_summary,
        )

        await status_msg.edit_text("✅ Baholash yakunlandi!")
        await safe_send(message, f"📘 Qism: {PART_LABELS[session.part]}")
        if session.question_text:
            await safe_send(message, f"❓ Savol:\n\n{session.question_text}")
        await safe_send(message, f"📝 *Transkript:*\n\n{full_transcript}")
        await safe_send(message, f"🎧 *Audio signallari:*\n{audio_summary}")
        await safe_send(message, report, reply_markup=DONATE_BUTTON)

        _save_to_history(user_id, session.part, report)
        await _record_activity_and_achievements(user_id, message, session.part, report)

        overall_text = _build_overall_score_text(user_id)
        if overall_text is not None:
            await message.answer(
                "🎉 Siz Speaking imtihonining barcha 4 qismini (1.1, 1.2, 2, 3) "
                "yakunladingiz!"
            )
            await message.answer(overall_text)
            await _grant_and_notify(user_id, "all_parts",
                                    message.from_user.first_name or "Foydalanuvchi")

    except Exception as e:
        logger.exception("Baholashda xatolik")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")

    finally:
        _cleanup_files(user_id)
        session.audio_files = []


_SCORE_PATTERN = re.compile(r"RASMIY BALL:\s*(\d+)\s*/\s*(\d+)")

# Har bir foydalanuvchining har bir qism bo'yicha ENG SO'NGGI xom balli
# (RAMda saqlanadi). Masalan: {user_id: {"1.1": 4, "2": 3}}
user_latest_scores: dict[int, dict] = defaultdict(dict)


def _save_to_history(user_id: int, part: str, report: str):
    """Baholash natijasidan qisqa xulosa qatorini (odatda 'RASMIY BALL: ...')
    ajratib olib, foydalanuvchi tarixiga qo'shadi. Shuningdek, agar
    natijada raqamli ball (X/Y) topilsa, uni umumiy 75-ballik hisob-kitob
    uchun alohida saqlaydi."""
    first_line = report.strip().splitlines()[0] if report.strip() else "Natija mavjud emas"
    entry = {
        "part": part,
        "score_line": first_line,
        "when": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    history = user_history[user_id]
    history.append(entry)
    if len(history) > MAX_HISTORY_PER_USER:
        del history[0 : len(history) - MAX_HISTORY_PER_USER]

    match = _SCORE_PATTERN.search(report)
    if match:
        raw_score = int(match.group(1))
        user_latest_scores[user_id][part] = raw_score


async def _record_activity_and_achievements(user_id: int, message: Message, part: str, report: str):
    """Baholash yakunlanganda: natijani bazaga yozadi, streak'ni yangilaydi
    va tegishli yutuqlarni beradi. Har qanday xatolik baholash oqimiga
    ta'sir qilmasligi uchun alohida ushlanadi."""
    name = message.from_user.first_name or message.from_user.username or "Foydalanuvchi"

    match = _SCORE_PATTERN.search(report)
    score = int(match.group(1)) if match else 0
    max_score = int(match.group(2)) if match else MAX_RAW_SCORES.get(part, 5)

    try:
        await sdb.save_result(user_id, name, part, score, max_score)
    except Exception:
        logger.exception("Natijani bazaga yozishda xatolik")

    # Birinchi test yutug'i
    await _grant_and_notify(user_id, "first_test", name)

    # Yuqori natija yutug'i (maksimal ballga yaqin)
    if max_score and score >= max_score - 1 and score > 0:
        await _grant_and_notify(user_id, "high_score", name)

    # Streak
    try:
        streak_info = await sdb.update_streak(user_id)
        if streak_info["is_new_day"]:
            current = streak_info["current_streak"]
            if current > 1:
                await message.answer(f"🔥 Streak: <b>{current} kun</b> ketma-ket! Ajoyib davom etyapsiz.",
                                     parse_mode="HTML")
            await _check_streak_achievements(user_id, current, name)
    except Exception:
        logger.exception("Streak yangilashda xatolik")


@dp.message(F.text == "📈 Mening natijalarim")
async def cmd_history(message: Message):
    user_id = message.from_user.id
    history = user_history.get(user_id, [])

    if not history:
        await message.answer(
            "Hali hech qanday baholash tarixingiz yo'q. "
            "\"📚 Qism tanlash\" orqali mashqni boshlang."
        )
        return

    lines = ["📈 Sizning oxirgi natijalaringiz:\n"]
    for entry in reversed(history[-10:]):
        part_label = PART_LABELS.get(entry["part"], entry["part"])
        lines.append(f"{entry['when']} — {part_label}\n{entry['score_line']}\n")

    await message.answer("\n".join(lines))


def _build_overall_score_text(user_id: int) -> str | None:
    """Foydalanuvchining barcha 4 qism bo'yicha eng so'nggi ballaridan
    umumiy 75-ballik natija matnini tayyorlaydi. Agar biror qism hali
    baholanmagan bo'lsa, None qaytaradi."""
    scores = user_latest_scores.get(user_id, {})
    missing = [p for p in MAX_RAW_SCORES if p not in scores]
    if missing:
        return None

    result = compute_overall(scores)
    lines = [
        "📊 Umumiy natija (75 ballik tizimda):\n",
        f"Xom ball: {result['raw_total']}/{result['max_raw_total']}",
        f"Taxminiy umumiy ball: {result['scaled_score']}/75",
        f"Taxminiy CEFR daraja: {result['band']}\n",
        "⚠️ Diqqat: bu — TAXMINIY hisob-kitob (oddiy proporsional formula). "
        "Rasmiy DTM/UZBMB imtihonida xom ballar maxsus statistik model "
        "(Rasch) orqali 75 ballga aylantiriladi, bu jadval ochiq e'lon "
        "qilinmagan. Shuning uchun bu ball rasmiy natijangizni "
        "ALMASHTIRMAYDI, faqat taxminiy yo'nalish beradi.\n",
        "Har bir qism bo'yicha eng so'nggi xom ballaringiz:",
    ]
    for part in ["1.1", "1.2", "2", "3"]:
        lines.append(f"  {PART_LABELS[part]}: {scores[part]}/{MAX_RAW_SCORES[part]}")

    return "\n".join(lines)


@dp.message(F.text == "📊 Umumiy ball (75)")
async def cmd_overall_score(message: Message):
    user_id = message.from_user.id
    text = _build_overall_score_text(user_id)

    if text is None:
        scores = user_latest_scores.get(user_id, {})
        missing = [p for p in MAX_RAW_SCORES if p not in scores]
        missing_labels = ", ".join(PART_LABELS[p] for p in missing)
        await message.answer(
            "Umumiy (75 ballik) natijani ko'rish uchun barcha 4 qismni "
            "kamida bir marta yakunlashingiz kerak.\n\n"
            f"Hali baholanmagan qism(lar): {missing_labels}"
        )
        return

    await message.answer(text)


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_question(message: Message):
    """Agar bot savol kutayotgan bo'lsa (awaiting_question=True), kelgan
    matnni savol sifatida qabul qiladi (yoki, agar oldin rasm yuborilgan
    bo'lsa, unga qo'shimcha sifatida biriktiradi). Bu handler eng oxirida
    ro'yxatdan o'tkaziladi, chunki u har qanday erkin matnga mos keladi —
    undan oldin ro'yxatdan o'tgan aniqroq handlerlar (tugmalar, buyruqlar)
    birinchi bo'lib ishga tushadi."""
    user_id = message.from_user.id
    session = user_sessions[user_id]

    if not session.awaiting_question:
        # Savol kutilmayapti — bu erkin matn, eslatma beramiz
        if session.part is None:
            await message.answer(
                "Boshlash uchun \"📚 Qism tanlash\" tugmasini bosing 👇",
                reply_markup=MAIN_KB,
            )
        return

    new_text = message.text.strip()
    if session.question_text:
        session.question_text += f"\n\n{new_text}"
    else:
        session.question_text = new_text

    await message.answer(
        "✅ Qabul qilindi. Yana savol/matn qo'shishingiz mumkin, yoki "
        "to'g'ridan-to'g'ri ovozli javob yuboring 🎙",
        reply_markup=MAIN_KB,
    )


async def safe_send(message: Message, text: str, **kwargs):
    """Xabarni Markdown bilan yuborishga urinadi; agar model javobidagi
    maxsus belgilar (*, _, ` va h.k.) muvozanatsiz bo'lib, Telegram
    formatlashni rad etsa, oddiy matn sifatida qayta yuboradi. Bu LLM
    javobidagi kutilmagan belgilar tufayli bot ishdan chiqishining oldini
    oladi."""
    try:
        return await message.answer(text, parse_mode="Markdown", **kwargs)
    except TelegramBadRequest:
        return await message.answer(text, parse_mode=None, **kwargs)


def _cleanup_files(user_id: int):
    session = user_sessions.get(user_id)
    if not session:
        return
    for path in session.audio_files:
        try:
            os.remove(path)
        except OSError:
            pass


async def health_check(request: web.Request) -> web.Response:
    """Render (va boshqa xizmatlar) shu manzilga so'rov yuborib, dastur
    ishlab turganini tekshiradi. Tashqi 'uptime ping' xizmatlari ham
    servisni uxlab qolishdan saqlash uchun shu manzilga so'rov yuboradi."""
    return web.Response(text="OK - CEFR Speaking bot ishlab turibdi")


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health-check server {PORT}-portda ishga tushdi")


# ---------------------------------------------------------------------------
# KANAL: ta'lim kontenti (idiom / phrasal verb / grammatika) avtomatik post
# ---------------------------------------------------------------------------
async def _post_lesson_to_channel(data: dict, emoji: str, kind_label: str):
    """Tayyor lesson ma'lumotini (title/explanation/examples/quiz) kanalga
    joylaydi: avval tushuntirish xabari, keyin 4 ta quiz-so'rovnoma."""
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID sozlanmagan, kanal posti o'tkazib yuborildi.")
        return

    text = channel_content.format_lesson_message(data, emoji, kind_label)
    text += _channel_footer()
    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

    for q in data.get("quiz", [])[:4]:
        options = q.get("options", [])
        if len(options) < 2:
            continue
        try:
            await bot.send_poll(
                chat_id=CHANNEL_ID,
                question=q["question"][:300],
                options=[opt[:100] for opt in options],
                type="quiz",
                correct_option_id=int(q.get("correct_index", 0)),
                explanation=(q.get("explanation") or "")[:200],
                is_anonymous=True,
            )
        except Exception:
            logger.exception("Quiz so'rovnomasini yuborishda xatolik")


def _channel_footer() -> str:
    """Har bir kanal postiga qo'shiladigan, kanalga qaytib olib boruvchi
    havola (post forward qilinganda ham manba ko'rinib tursin uchun)."""
    if not CHANNEL_ID:
        return ""
    username = CHANNEL_ID.lstrip("@")
    return f"\n\n━━━━━━━━━━━━━━━━━━\n📢 @{username} | t.me/{username}"


async def post_idiom_lesson():
    try:
        data = await channel_content.generate_idiom_lesson()
        await _post_lesson_to_channel(data, "💬", "Kunlik Idiom")
    except Exception:
        logger.exception("Idiom postini generatsiya/yuborishda xatolik")


async def post_morning_greeting():
    """Har kuni ertalab (Toshkent vaqti bilan 07:00) kanal a'zolariga
    ingliz tilida salom va ezgu tilaklar, hamda ilhomlantiruvchi rasm bilan
    yuboradi — kunni ijobiy kayfiyat bilan boshlash uchun."""
    if not CHANNEL_ID:
        return
    try:
        text = await channel_content.generate_morning_greeting()
        caption = f"☀️ <b>Good morning!</b>\n\n{text}{_channel_footer()}"

        try:
            photo_url = await get_random_morning_photo()
        except Exception:
            logger.exception("Ertalabki rasm olishda xatolik, faqat matn yuboriladi")
            photo_url = None

        if photo_url:
            await bot.send_photo(CHANNEL_ID, photo=photo_url, caption=caption[:1024], parse_mode="HTML")
        else:
            await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML")
    except Exception:
        logger.exception("Ertalabki salomlashish postini yuborishda xatolik")


async def post_idea_bank():
    """Speaking Part 3 / Writing Task 2 uchun fikr-argument boyitish
    materialini kanalga joylaydi. HOZIRCHA sinov bosqichida — avtomatik
    jadvalga qo'shilmagan, faqat /post_ideas admin buyrug'i orqali ishga
    tushiriladi."""
    if not CHANNEL_ID:
        return
    try:
        data = await channel_content.generate_idea_bank()
        text = channel_content.format_idea_bank_message(data) + _channel_footer()
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except Exception:
        logger.exception("Fikr banki postini generatsiya/yuborishda xatolik")


async def post_phrasal_verb_lesson():
    try:
        data = await channel_content.generate_phrasal_verb_lesson()
        await _post_lesson_to_channel(data, "🔗", "Kunlik Phrasal Verb")
    except Exception:
        logger.exception("Phrasal verb postini generatsiya/yuborishda xatolik")


async def post_grammar_lesson():
    try:
        level = channel_content.get_grammar_level_for_today()
        data = await channel_content.generate_grammar_lesson(level)
        await _post_lesson_to_channel(data, "📘", "Grammatika darsi")
    except Exception:
        logger.exception("Grammatika postini generatsiya/yuborishda xatolik")


async def post_weekly_leaderboard():
    """Har hafta kanalga eng yaxshi natijalar reytingini joylaydi —
    musobaqa ruhini va yangi a'zolar uchun ijtimoiy isbotni kuchaytiradi."""
    if not CHANNEL_ID:
        return
    try:
        weekly = await sdb.get_weekly_leaderboard(10)
        streaks = await sdb.get_streak_leaderboard(5)
    except Exception:
        logger.exception("Haftalik reytingni olishda xatolik")
        return

    if not weekly and not streaks:
        logger.info("Haftalik reyting bo'sh, post o'tkazib yuborildi.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>HAFTANING NATIJALARI</b>\n"]

    if weekly:
        lines.append("<b>📊 Eng yuqori o'rtacha ball</b>")
        for i, row in enumerate(weekly):
            prefix = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{prefix} {row['user_name']} — {row['avg_percent']}%")

    if streaks:
        lines.append("\n<b>🔥 Eng izchil mashq qilganlar</b>")
        for i, row in enumerate(streaks):
            prefix = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{prefix} {row['user_name']} — {row['current_streak']} kun")

    bot_info = await bot.get_me()
    lines.append(
        f"\n━━━━━━━━━━━━━━━━━━\n"
        f"Siz ham qatnashing — bepul mashq qiling:\n👉 @{bot_info.username}"
    )

    try:
        await bot.send_message(CHANNEL_ID, "\n".join(lines) + _channel_footer(), parse_mode="HTML")
    except Exception:
        logger.exception("Haftalik reyting postini yuborishda xatolik")


# --- Admin uchun qo'lda ishga tushirish buyruqlari (sinov/favqulodda uchun) ---
@dp.message(Command("post_idiom"))
async def cmd_post_idiom(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ Idiom posti tayyorlanmoqda...")
    await post_idiom_lesson()
    await message.answer("✅ Kanalga joylandi (agar xatolik bo'lmasa).")


@dp.message(Command("post_morning"))
async def cmd_post_morning(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ Ertalabki salomlashish tayyorlanmoqda...")
    await post_morning_greeting()
    await message.answer("✅ Kanalga joylandi (agar xatolik bo'lmasa).")


@dp.message(Command("post_ideas"))
async def cmd_post_ideas(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ Fikr banki tayyorlanmoqda...")
    await post_idea_bank()
    await message.answer("✅ Kanalga joylandi (agar xatolik bo'lmasa). Bu HOZIRCHA faqat qo'lda ishga tushadi.")


@dp.message(Command("post_phrasal"))
async def cmd_post_phrasal(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ Phrasal verb posti tayyorlanmoqda...")
    await post_phrasal_verb_lesson()
    await message.answer("✅ Kanalga joylandi (agar xatolik bo'lmasa).")


@dp.message(Command("post_grammar"))
async def cmd_post_grammar(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ Grammatika darsi tayyorlanmoqda...")
    await post_grammar_lesson()
    await message.answer("✅ Kanalga joylandi (agar xatolik bo'lmasa).")


@dp.message(Command("post_leaderboard"))
async def cmd_post_leaderboard(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ Haftalik reyting tayyorlanmoqda...")
    await post_weekly_leaderboard()
    await message.answer("✅ Kanalga joylandi (agar ma'lumot bo'lsa).")


# --- Kunlik avtomatik rejalashtiruvchi (scheduler) ---
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
_CHANNEL_SCHEDULE = [
    (7, 0, post_morning_greeting),
    (9, 0, post_idiom_lesson),
    (14, 0, post_grammar_lesson),
    (20, 0, post_phrasal_verb_lesson),
]


async def channel_scheduler():
    """Har daqiqada joriy vaqtni (Toshkent bo'yicha) tekshirib, jadvaldagi
    vaqt kelganda tegishli postni bir marta (kuniga bitta) yuboradi.
    Haftalik reyting esa faqat yakshanba kuni soat 21:00 da joylanadi."""
    last_sent_date = {i: None for i in range(len(_CHANNEL_SCHEDULE))}
    last_leaderboard_date = None
    logger.info("Kanal rejalashtiruvchisi ishga tushdi (Asia/Tashkent vaqti bo'yicha).")
    while True:
        try:
            now = datetime.now(TASHKENT_TZ)
            for i, (hour, minute, func) in enumerate(_CHANNEL_SCHEDULE):
                if now.hour == hour and now.minute == minute and last_sent_date[i] != now.date():
                    last_sent_date[i] = now.date()
                    logger.info(f"Rejalashtirilgan post ishga tushmoqda: {func.__name__}")
                    await func()

            # Haftalik reyting — yakshanba (weekday() == 6) soat 21:00 da
            if (now.weekday() == 6 and now.hour == 21 and now.minute == 0
                    and last_leaderboard_date != now.date()):
                last_leaderboard_date = now.date()
                logger.info("Haftalik reyting posti ishga tushmoqda")
                await post_weekly_leaderboard()
        except Exception:
            logger.exception("channel_scheduler ichida xatolik")
        await asyncio.sleep(30)


async def main():
    logger.info("Bot ishga tushdi...")
    try:
        await sdb.init_db()
        logger.info("Ma'lumotlar bazasi tayyor")
    except Exception:
        logger.exception("Bazani ishga tushirishda xatolik — bot baribir ishlaydi, "
                         "lekin referal/streak/reyting funksiyalari ishlamasligi mumkin")
    await start_health_server()
    asyncio.create_task(channel_scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
