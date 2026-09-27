# -*- coding: utf-8 -*-
"""
Yutuqlar (achievements) tizimi: foydalanuvchi ma'lum bosqichlarga
erishganda avtomatik beriladigan nishonlar va ular uchun "sertifikat"
matni (ulashish uchun mo'ljallangan).
"""

BOT_USERNAME = "Speaking_baholashBot"

# achievement_key -> (emoji, nomi, tavsifi)
ACHIEVEMENTS = {
    # Streak bo'yicha
    "streak_3": ("🔥", "Boshlovchi olov", "3 kun ketma-ket mashq qildingiz"),
    "streak_7": ("🔥", "Haftalik izchillik", "7 kun ketma-ket mashq qildingiz"),
    "streak_30": ("💎", "Po'lat irodа", "30 kun ketma-ket mashq qildingiz"),

    # Referal bo'yicha
    "referral_1": ("🤝", "Birinchi do'st", "1 ta do'stingizni taklif qildingiz"),
    "referral_5": ("🌟", "Ilhomlantiruvchi", "5 ta do'stingizni taklif qildingiz"),
    "referral_20": ("👑", "Jamoa yetakchisi", "20 ta do'stingizni taklif qildingiz"),

    # Natija bo'yicha
    "first_test": ("🎯", "Birinchi qadam", "Birinchi Speaking testini yakunladingiz"),
    "all_parts": ("🏅", "To'liq imtihon", "Barcha 4 qismni yakunladingiz"),
    "high_score": ("⭐", "Yuqori natija", "Bir qismda maksimal ballga yaqin natija oldingiz"),
}


def format_achievement_message(achievement_key: str, user_name: str) -> str | None:
    """Yutuq berilganda foydalanuvchiga yuboriladigan tabrik xabari."""
    item = ACHIEVEMENTS.get(achievement_key)
    if not item:
        return None
    emoji, title, description = item
    return (
        f"{emoji} <b>Yangi yutuq!</b>\n\n"
        f"<b>{title}</b>\n"
        f"{description}\n\n"
        f"Tabriklaymiz, {user_name}! Shu ruhda davom eting 💪"
    )


def format_certificate(user_name: str, achievements: list, current_streak: int,
                       referral_count: int) -> str:
    """Foydalanuvchining barcha yutuqlaridan iborat, ulashishga mo'ljallangan
    'sertifikat' matni."""
    if achievements:
        lines = []
        for a in achievements:
            item = ACHIEVEMENTS.get(a["achievement_key"])
            if item:
                emoji, title, _ = item
                lines.append(f"{emoji} {title}")
        badges = "\n".join(lines)
    else:
        badges = "Hozircha yutuqlar yo'q — birinchisini qo'lga kiriting!"

    return (
        f"🏆 <b>MENING NATIJALARIM</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>{user_name}</b>\n\n"
        f"🔥 Joriy streak: <b>{current_streak} kun</b>\n"
        f"🤝 Taklif qilganlar: <b>{referral_count} kishi</b>\n\n"
        f"<b>Yutuqlarim:</b>\n{badges}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"CEFR Multilevel Speaking'ni bepul mashq qiling:\n"
        f"👉 @{BOT_USERNAME}"
    )
