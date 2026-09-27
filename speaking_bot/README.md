CEFR Speaking Baholovchi Telegram Bot
CEFR Multilevel imtihonining Gapirish (Speaking) qismini avtomatik
baholaydigan Telegram bot. Foydalanuvchi ovozli xabar yuboradi → bot uni
matnga aylantiradi (Groq'ning bepul Whisper API'si) → berilgan CEFR
rubrikasi asosida baholaydi (Groq'ning bepul Llama 3.3 70B modeli) →
natijani va izohni qaytaradi.
Butunlay BEPUL ishlaydi — Groq API kredit karta talab qilmaydi.
Ishlash tartibi
Foydalanuvchi `/start` bosadi.
"📚 Qism tanlash" tugmasi orqali imtihon qismini tanlaydi:
Part 1.1 (A1/A2), Part 1.2 (A2/B1), Part 2 (B1/B2), yoki Part 3 (B2/C1).
Shu qism uchun savolni matn yoki rasm (screenshot) ko'rinishida
yuboradi. Rasmdagi savol Groq'ning vizual (vision) modeli orqali
avtomatik o'qiladi.
Savolga bir yoki bir nechta ovozli xabar (voice message) tarzida javob
beradi.
"✅ Yakunlash va baholash" tugmasini bosadi.
Bot:
Har bir audio xabarni Groq'ning Whisper API'si orqali matnga aylantiradi va
pauza/gapirish tezligi/akustik ishonch kabi audio signallarini hisoblaydi.
To'liq transkript, savol matni va audio signallarini Groq'ning til
modeliga TANLANGAN QISMGA mos rasmiy rubrika bilan yuboradi.
Rasmiy ball shkalasi bo'yicha baho, 4 mezon (Pronunciation, Accuracy,
Fluency, Lexical Resource) bo'yicha batafsil tahlil, kuchli va
rivojlantirish kerak bo'lgan tomonlarni qaytaradi.
O'rnatish
```bash
cd cefr_bot
pip install -r requirements.txt
cp .env.example .env
# .env faylini tahrirlab, o'z API kalitlaringizni kiriting
```
Kerakli API kalitlar
Kalit	Qayerdan olinadi	Narxi
`TELEGRAM_BOT_TOKEN`	Telegram'da @BotFather orqali yangi bot yarating	Bepul
`GROQ_API_KEY`	https://console.groq.com/keys (email bilan ro'yxatdan o'ting, "Create API Key" bosing)	Bepul, karta shart emas
Ishga tushirish
```bash
python bot.py
```
Fayl tuzilishi
```
cefr_bot/
├── bot.py            # Asosiy Telegram bot logikasi (aiogram)
├── transcriber.py     # Whisper API orqali audio → matn
├── evaluator.py        # Groq til modeli orqali CEFR baholash
├── vision.py            # Groq vizual modeli orqali rasmdan savol o'qish
├── rubric.py             # 4 qism uchun rasmiy CEFR baholash mezonlari
├── config.py              # Muhit o'zgaruvchilarini yuklash
├── requirements.txt
├── .env.example
└── README.md
```
Narxlar
Butunlay bepul — Groq API kredit karta talab qilmaydi va token/vaqt
bo'yicha to'lov olmaydi. Faqat so'rovlar soniga cheklov (rate limit) bor:
kuniga ~14,400 so'rov, daqiqasiga ~30 so'rov. Shaxsiy yoki kichik guruh
(sinf, kurs) uchun bu cheklov yetarlicha keng.
Agar kelajakda yuqoriroq sifat kerak bo'lsa (masalan Claude yoki GPT-4
darajasidagi nozik baholash), `evaluator.py` faylini Anthropic yoki OpenAI
API'ga qaytarish mumkin — bunda pullik hisob kerak bo'ladi.
Kengaytirish g'oyalari
Ma'lumotlar bazasi: foydalanuvchilar tarixini saqlash (SQLite/Postgres)
Rasmiy savollar banki: har safar tasodifiy 3 ta savol yuborish
Admin panel: statistikani ko'rish, natijalarni eksport qilish
Ovoz sifatini tekshirish: juda qisqa/sifatsiz audio uchun ogohlantirish
Vaqt chegarasi: har bir javobga max vaqt qo'yish (real imtihon kabi)
Webhook rejimi: polling o'rniga webhook orqali production'da ishlatish
(masalan Railway, Render, yoki VPS'da)
Botni Render.com'da doimiy (24/7) ishga tushirish (bepul, karta shart emas)
Bot kodi ichida kichik "hayotdalik" (health-check) veb-server ham bor
(`bot.py`dagi `start_health_server`), bu Render'ning "Web Service" turida
ishlashi uchun kerak.
1. GitHub'ga yuklash
GitHub'da yangi repository yarating (masalan `cefr-bot`)
`cefr_bot` papkasidagi barcha fayllarni (`.env`dan tashqari!) shu repoga yuklang
Muhim: `.env` faylini hech qachon GitHub'ga yuklamang — u yerda maxfiy tokenlar bor
2. Render'da deploy qilish
https://render.com ga kiring, GitHub hisobingiz bilan ro'yxatdan o'ting
"New +" → "Web Service" tanlang
GitHub repongizni ulang
Sozlamalar:
Runtime: Python 3
Build Command: `pip install -r requirements.txt`
Start Command: `python bot.py`
Instance Type: Free
"Environment" bo'limida quyidagi o'zgaruvchilarni qo'shing (`.env` faylidagi kabi):
`TELEGRAM_BOT_TOKEN` = sizning tokeningiz
`GROQ_API_KEY` = sizning Groq kalitingiz
"Create Web Service" tugmasini bosing
3. Uxlab qolishning oldini olish (UptimeRobot)
Render'ning bepul tarifi 15 daqiqa harakatsizlikdan keyin "uxlab qoladi".
Buni oldini olish uchun:
https://uptimerobot.com ga kiring, bepul ro'yxatdan o'ting
"Add New Monitor" → turi: HTTP(s)
URL: Render bergan manzilingiz (masalan `https://cefr-bot.onrender.com/health`)
Tekshirish oralig'i: 5 daqiqa
Saqlang — endi UptimeRobot har 5 daqiqada botingizga "salom" berib, uni uyg'oq ushlab turadi
Shu bilan bot to'liq bepul, 24/7 ishlab turadi — kompyuteringiz o'chiq bo'lsa ham!
Eslatma yordamchi baholash vositasi sifatida mo'ljallangan — rasmiy imtihon
natijalarini almashtirmaydi. AI baholash inson ekspert bahosiga 100% mos
kelmasligi mumkin, ayniqsa chegara balllarida.
