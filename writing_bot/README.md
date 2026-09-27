# Multilevel CEFR Writing — baholash boti

Telegram bot: foydalanuvchi **Task 1.1** (norasmiy email, B1), **Task 1.2**
(rasmiy email, B2) yoki **Task 2** (blog/forum posti, C1) tugmasidan birini
tanlaydi, matnini yuboradi, bot esa Claude API orqali berilgan CEFR mezoni
asosida baholab, ball + izoh qaytaradi. Uchala vazifa bajarilgach, umumiy
**Standard ball (0–75)** ham chiqariladi.

## 1. O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Sozlash

`.env.example` faylini `.env` deb nusxalang va haqiqiy qiymatlarni kiriting:

```bash
cp .env.example .env
```

`.env` ichida:
- `BOT_TOKEN` — @BotFather dan olingan token.
- `ANTHROPIC_API_KEY` — console.anthropic.com dan olinadigan API kalit
  (baholash aynan shu kalit orqali Claude'ga so'rov yuboradi).
- `CLAUDE_MODEL` — ixtiyoriy, standart `claude-sonnet-5`.

**Xavfsizlik:** `.env` faylini hech qachon ochiq joyga (GitHub public repo,
chat va h.k.) yubormang. Agar token allaqachon kimgadir ko'rsatilgan bo'lsa,
@BotFather orqali `/revoke` qilib, yangisini oling.

## 3. Ishga tushirish

```bash
python3 bot.py
```

Bot polling rejimida ishlaydi (serverga webhook sozlash shart emas).

## 4. Loyihaning tuzilishi

```
cefr_writing_bot/
├── bot.py          # Telegram bot logikasi (aiogram 3.x)
├── evaluator.py     # Claude API chaqiruvi va JSON javobni tahlil qilish
├── rubrics.py        # Vazifa tavsiflari, baholash shkalalari, standart ball jadvali
├── requirements.txt
├── .env.example
└── README.md
```

## 5. Baholash mantig'i

Har bir vazifa uchun (`rubrics.py`) alohida holistik shkala mavjud:

| Vazifa | Maqsad daraja | Hajm | Shkala |
|---|---|---|---|
| Task 1.1 | B1 | ~50 so'z | 0–5 |
| Task 1.2 | B2 | 120–150 so'z | 0–5 |
| Task 2 | C1 | 180–200 so'z | 0–6 |

Uchta ball yig'indisi (max 16) hujjatdagi jadval asosida 0–75 oralig'idagi
Standard ballga aylantiriladi (`get_standard_score`).

> **Eslatma:** shkaladagi 0–5/0–6 pog'onalarning batafsil tavsifi (masalan,
> "3–4 ball nima uchun beriladi") asl hujjatda faqat qisman berilgan edi
> (faqat qaysi ball qaysi CEFR darajasiga mos kelishi ko'rsatilgan). Har bir
> pog'ona uchun to'liq tavsifni CEFR umumiy mezonlari asosida men to'ldirdim
> — agar sizda rasmiy, to'liq band-descriptor matni bo'lsa, `rubrics.py`
> dagi `rubric` matnlarini o'sha asl matn bilan almashtirish tavsiya etiladi,
> bu baholash sifatini yanada oshiradi.

## 6. Kengaytirish g'oyalari

- Natijalarni SQLite/Postgres bazasida saqlash (hozir xotirada, bot
  qayta ishga tushsa yo'qoladi).
- O'qituvchi/administrator uchun barcha o'quvchilar natijalarini ko'rish paneli.
- Bir nechta urinishni solishtirish, progress grafigi.
- Fayl (docx/pdf) shaklida yuborilgan matnlarni ham qabul qilish.
