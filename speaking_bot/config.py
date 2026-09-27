import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Groq — bepul, kartasiz API. https://console.groq.com/keys dan oling.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# CEFR baholash uchun ishlatiladigan til modeli (Groq bepul katalogida mavjud).
# Eslatma: avval llama-3.3-70b-versatile ishlatilgan edi, lekin Groq uni
# 2026-yil 16-avgustda butunlay o'chiradi. Shuning uchun Groq tavsiya qilgan
# openai/gpt-oss-120b modeliga o'tkazildi (2026-08).
GROQ_CHAT_MODEL = "openai/gpt-oss-120b"

# Rasm orqali yuborilgan savolni o'qish uchun ishlatiladigan vizual model.
# Eslatma: avval meta-llama/llama-4-scout ishlatilar edi, lekin Groq uni
# ham eskirgan deb e'lon qilib, qwen/qwen3.6-27b ga o'tkazishni tavsiya
# qildi (hozircha "preview" holatida).
GROQ_VISION_MODEL = "qwen/qwen3.6-27b"

# Part 1.2 uchun tasodifiy surat juftlari olish uchun Unsplash'ning bepul
# API kaliti. https://unsplash.com/developers dan bepul oling (karta shart
# emas). Agar bo'sh qoldirilsa, "🎲 Tasodifiy savol" Part 1.2 uchun
# ishlamaydi (foydalanuvchi shunchaki o'zi rasm yuklashi kerak bo'ladi).
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

# Audio -> matn uchun ishlatiladigan Whisper modeli (Groq bepul katalogida mavjud)
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

# Ta'lim kontenti (idiom/phrasal verb/grammatika) avtomatik joylanadigan
# Telegram kanali. Kanal username (masalan "@mening_kanalim") yoki raqamli
# ID (masalan "-1001234567890") bo'lishi mumkin. Bot shu kanalga ADMIN
# sifatida ("Post messages" ruxsati bilan) qo'shilgan bo'lishi shart.
# Agar bo'sh qoldirilsa, avtomatik kanal posti o'chirilgan bo'ladi.
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN topilmadi. .env faylini tekshiring.")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY topilmadi. .env faylini tekshiring.")
