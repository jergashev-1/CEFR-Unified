"""
🎧 Shadowing mashqi moduli.

Ochiq manbalardan (VOA Learning English, BBC Learning English va h.k.)
oldindan tayyorlangan qisqa (4-8 soniyalik) audio segmentlar orqali
talaffuzni "shadowing" texnikasi bilan mashq qildiradi:

1. Bot original (native) so'zlovchi audiosini yuboradi.
2. Foydalanuvchi xuddi shunday ohang, tezlik va urg'u bilan takrorlab,
   ovozli xabar yuboradi.
3. Foydalanuvchi ovozi mavjud `transcriber.transcribe_audio()` (Groq
   Whisper — botda CEFR baholash uchun ham ishlatiladigan xizmat) orqali
   matnga o'giriladi.
4. Aytilgan matn originali bilan so'z darajasida solishtiriladi
   (difflib) va gapirish tezligi (wpm) taqqoslanadi.
5. Foydalanuvchiga aniqlik foizi, farq qilgan so'zlar va tezlik bo'yicha
   qisqa fikr-mulohaza qaytariladi. Kunlik streak (ketma-ket kunlar)
   hisoblanadi.

Kutubxona (audio + transkript) `build_shadowing_library.py` orqali
oldindan tayyorlanadi va shadowing_data/manifest.json faylida saqlanadi.

INTEGRATSIYA (bot.py ga qo'shish uchun):
    import shadowing
    ...
    dp = Dispatcher()
    dp.include_router(shadowing.router)   # <-- bu qatorni boshqa
                                           #     @dp.message(...) larGA
                                           #     QADAR, dp yaratilgan
                                           #     zahoti qo'shing!

Bundan tashqari, MAIN_KB ga "🎧 Shadowing mashqi" tugmasini qo'shing —
batafsili SHADOWING_INTEGRATION.md faylida.
"""
import difflib
import logging
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from shadowing_library import (
    ShadowingSegment,
    get_random_segment,
    get_segment_by_id,
    library_size,
)
from transcriber import transcribe_audio

logger = logging.getLogger(__name__)
router = Router(name="shadowing")

# CEFR darajalari — soddadan murakkabga qarab, foydalanuvchi shu ketma-ketlikda
# avtomatik ilgarilaydi.
CEFR_LEVELS = ["A2", "A2+", "B1", "B1+", "B2", "B2+", "C1"]

# Bir darajadan keyingisiga o'tish uchun: kamida shuncha segment bajarilgan
# bo'lishi va ularning o'rtacha o'xshashlik foizi shu chegaradan yuqori
# bo'lishi kerak.
LEVEL_UP_MIN_ATTEMPTS = 3
LEVEL_UP_MIN_AVG_SCORE = 75.0


@dataclass
class ShadowingUserState:
    current_segment_id: str | None = None
    transcript_shown: bool = False
    last_practice_date: date | None = None
    streak_days: int = 0
    best_scores: dict = field(default_factory=dict)  # segment_id -> eng yaxshi %
    level_index: int = 0  # CEFR_LEVELS ichidagi joriy daraja indeksi
    level_scores: list = field(default_factory=list)  # joriy darajadagi so'nggi natijalar

    @property
    def current_level(self) -> str:
        return CEFR_LEVELS[self.level_index]


# Har bir foydalanuvchi uchun shadowing holati (RAMda saqlanadi)
shadowing_state: dict[int, ShadowingUserState] = defaultdict(ShadowingUserState)


def _segment_keyboard(segment_id: str, transcript_shown: bool) -> InlineKeyboardMarkup:
    toggle_text = "🙈 Matnni yashirish" if transcript_shown else "📝 Matnni ko'rsatish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"shadow_text:{segment_id}")],
            [InlineKeyboardButton(text="🔁 Boshqa segment", callback_data="shadow_next")],
        ]
    )


def _update_streak(state: ShadowingUserState) -> None:
    today = date.today()
    if state.last_practice_date == today:
        return  # bugun uchun allaqachon hisoblangan
    if state.last_practice_date == today - timedelta(days=1):
        state.streak_days += 1
    else:
        state.streak_days = 1
    state.last_practice_date = today


async def _send_segment(bot: Bot, chat_id: int, user_id: int, segment: ShadowingSegment) -> None:
    state = shadowing_state[user_id]
    state.current_segment_id = segment.id
    state.transcript_shown = False

    caption = (
        f"🎧 Manba: {segment.source}\n"
        f"📶 Daraja: {state.current_level}\n"
        f"⏱ Davomiyligi: {segment.duration_sec:.1f}s · {segment.word_count} so'z\n\n"
        "Diqqat bilan tinglang, so'ng xuddi shunday ohang va tezlikda "
        "takrorlab, ovozli xabar yuboring 🎙"
    )
    await bot.send_voice(
        chat_id=chat_id,
        voice=FSInputFile(segment.full_audio_path),
        caption=caption,
        reply_markup=_segment_keyboard(segment.id, transcript_shown=False),
    )


@router.message(Command("shadowing"))
@router.message(F.text == "🎧 Shadowing mashqi")
async def cmd_shadowing(message: Message, bot: Bot) -> None:
    if library_size() == 0:
        await message.answer(
            "Hozircha shadowing kutubxonasi bo'sh. Admin "
            "`build_shadowing_library.py` skriptini ishga tushirishi kerak."
        )
        return

    user_id = message.from_user.id
    state = shadowing_state[user_id]
    segment = get_random_segment(level=state.current_level)
    await message.answer(
        "🎧 *Shadowing mashqi*\n\n"
        "Bu mashqda haqiqiy (native) so'zlovchi audiosini eshitib, xuddi "
        "soya kabi ortidan takrorlaysiz — bu talaffuz, ohang va tezlikni "
        "yaxshilashning eng samarali usullaridan biri.\n\n"
        f"📶 Sizning joriy darajangiz: *{state.current_level}*\n"
        "Har darajada bir necha segmentni yaxshi bajarsangiz, keyingi "
        "darajaga avtomatik o'tasiz.",
        parse_mode="Markdown",
    )
    await _send_segment(bot, message.chat.id, user_id, segment)


@router.callback_query(F.data == "shadow_next")
async def callback_next_segment(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id
    state = shadowing_state[user_id]
    segment = get_random_segment(level=state.current_level)
    if segment is None:
        await callback.answer("Kutubxona bo'sh.", show_alert=True)
        return
    await _send_segment(bot, callback.message.chat.id, user_id, segment)
    await callback.answer()


@router.callback_query(F.data.startswith("shadow_text:"))
async def callback_toggle_text(callback: CallbackQuery) -> None:
    segment_id = callback.data.split(":", 1)[1]
    segment = get_segment_by_id(segment_id)
    user_id = callback.from_user.id
    state = shadowing_state[user_id]

    if segment is None:
        await callback.answer("Segment topilmadi.", show_alert=True)
        return

    state.transcript_shown = not state.transcript_shown
    try:
        if state.transcript_shown:
            await callback.message.answer(f"📝 Matn:\n\n{segment.text}")
        await callback.message.edit_reply_markup(
            reply_markup=_segment_keyboard(segment_id, state.transcript_shown)
        )
    except Exception:
        pass
    await callback.answer()


def _word_diff_feedback(original: str, spoken: str) -> tuple[float, str]:
    """So'z darajasida solishtirib, o'xshashlik foizi va farqlar matnini
    qaytaradi."""
    orig_words = original.lower().split()
    spoken_words = spoken.lower().split()

    matcher = difflib.SequenceMatcher(a=orig_words, b=spoken_words)
    ratio = matcher.ratio() * 100

    marked = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            marked.extend(orig_words[i1:i2])
        elif tag == "replace":
            marked.append(f"[{'/'.join(orig_words[i1:i2])}→{'/'.join(spoken_words[j1:j2])}]")
        elif tag == "delete":
            marked.append(f"[✗{' '.join(orig_words[i1:i2])}]")
        elif tag == "insert":
            marked.append(f"[+{' '.join(spoken_words[j1:j2])}]")

    return ratio, " ".join(marked)


def _tempo_feedback(expected_wpm: float, actual_wpm: float) -> str:
    if expected_wpm <= 0 or actual_wpm <= 0:
        return ""
    ratio = actual_wpm / expected_wpm
    if ratio < 0.8:
        return "🐢 Original nutqqa nisbatan biroz sekinroq gapirdingiz — tezlikni oshiring."
    if ratio > 1.2:
        return "🐇 Original nutqqa nisbatan biroz tezroq gapirdingiz — birozgina sekinlashtiring."
    return "✅ Gapirish tezligingiz original nutqqa juda yaqin!"


def _register_attempt_and_maybe_level_up(state: ShadowingUserState, ratio: float) -> str | None:
    """Joriy darajadagi natijani qayd qiladi. Agar so'nggi bir necha
    urinishning o'rtacha natijasi yetarlicha yuqori bo'lsa, foydalanuvchini
    keyingi CEFR darajasiga o'tkazadi va yangi daraja nomini qaytaradi.
    Aks holda None qaytaradi."""
    state.level_scores.append(ratio)
    if len(state.level_scores) < LEVEL_UP_MIN_ATTEMPTS:
        return None

    recent = state.level_scores[-LEVEL_UP_MIN_ATTEMPTS:]
    avg_score = sum(recent) / len(recent)

    if avg_score >= LEVEL_UP_MIN_AVG_SCORE and state.level_index < len(CEFR_LEVELS) - 1:
        state.level_index += 1
        state.level_scores = []
        return state.current_level

    # Darajada qolamiz, lekin tarixni cheklab qo'yamiz (xotira shishmasin)
    state.level_scores = state.level_scores[-LEVEL_UP_MIN_ATTEMPTS:]
    return None


@router.message(F.voice)
async def handle_shadowing_voice(message: Message, bot: Bot) -> None:
    """
    MUHIM: bu handler `dp.include_router(shadowing.router)` orqali
    ro'yxatdan bot.py dagi asosiy `@dp.message(F.voice | F.audio)`
    (CEFR baholash) handleridan OLDIN o'tkazilishi kerak — buning uchun
    include_router chaqiruvini bot.py da `dp = Dispatcher()` qatoridan
    darhol keyin joylashtiring.

    Bu handler faqat foydalanuvchi hozir faol shadowing segmentiga ega
    bo'lsagina ishlaydi. Aks holda hech narsa qilmay chiqib ketadi —
    shunda aiogram xabarni navbatdagi mos handlerga (CEFR speaking
    modulidagi ovoz handleriga) uzatadi.
    """
    user_id = message.from_user.id
    state = shadowing_state.get(user_id)

    if state is None or state.current_segment_id is None:
        return

    segment = get_segment_by_id(state.current_segment_id)
    if segment is None:
        return

    status_msg = await message.answer("⏳ Ovozingiz tahlil qilinmoqda...")

    file = await bot.get_file(message.voice.file_id)
    local_path = os.path.join(
        tempfile.gettempdir(), f"shadow_{user_id}_{message.voice.file_id}.ogg"
    )
    await bot.download_file(file.file_path, destination=local_path)

    try:
        metrics = await transcribe_audio(local_path, language="en")
        ratio, diff_text = _word_diff_feedback(segment.text, metrics.text)
        tempo_note = _tempo_feedback(segment.expected_wpm, metrics.speaking_words_per_min)

        _update_streak(state)
        prev_best = state.best_scores.get(segment.id, 0.0)
        is_new_best = ratio > prev_best
        state.best_scores[segment.id] = max(ratio, prev_best)
        new_level = _register_attempt_and_maybe_level_up(state, ratio)

        if ratio >= 90:
            verdict = "🌟 Ajoyib! Deyarli aynan takrorladingiz."
        elif ratio >= 75:
            verdict = "👍 Yaxshi! Kichik farqlar bor."
        elif ratio >= 50:
            verdict = "🙂 Yomon emas, lekin yana mashq qiling."
        else:
            verdict = "💪 Qiyin bo'ldimi? Bir necha marta qayta tinglab, qayta urinib ko'ring."

        report = (
            f"{verdict}\n\n"
            f"🎯 O'xshashlik: {ratio:.0f}%\n"
            f"{tempo_note}\n\n"
            f"📝 *Original:*\n{segment.text}\n\n"
            f"🗣 *Siz aytdingiz:*\n{metrics.text}\n\n"
            f"🔍 *Farqlar:*\n{diff_text}\n\n"
            f"📶 Daraja: {state.current_level}\n"
            f"🔥 Ketma-ket kunlar: {state.streak_days}"
        )
        if is_new_best and prev_best > 0:
            report += f"\n🏆 Yangi rekord! (avvalgisi: {prev_best:.0f}%)"
        if new_level:
            report += f"\n\n🎉 Tabriklaymiz! Siz *{new_level}* darajasiga o'tdingiz!"

        await status_msg.delete()
        await message.answer(
            report,
            parse_mode="Markdown",
            reply_markup=_segment_keyboard(segment.id, state.transcript_shown),
        )
    except Exception as e:
        logger.exception("Shadowing ovozini tahlil qilishda xatolik")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass
