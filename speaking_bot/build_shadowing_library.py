"""
Ochiq manbalardagi audio materiallardan (VOA Learning English, BBC Learning
English, LibriVox va h.k.) shadowing mashqi uchun qisqa (4-8 soniyalik)
segmentlar kutubxonasini tayyorlaydigan OFFLINE skript.

Bu skript botning o'zi tomonidan ishga tushirilmaydi — admin (siz) uni
qo'lda, vaqti-vaqti bilan ishga tushirib, kutubxonani yangilaysiz:

    python build_shadowing_library.py

Ishlash tartibi:
1. SOURCES ro'yxatidagi har bir audio (to'g'ridan-to'g'ri video/audio
   havolasi) yt-dlp orqali yuklab olinadi (faqat audio, mp3 formatda).
2. pydub yordamida sukunat joylari (silence) aniqlanadi va audio tabiiy
   pauzalar bo'yicha bo'laklarga bo'linadi (gap o'rtasidan kesilib
   qolmasligi uchun).
3. 3.5-8.5 soniya oralig'idagi bo'laklar nomzod sifatida tanlanadi.
4. Har bir nomzod bo'lak mavjud `transcriber.transcribe_audio()` (Groq
   Whisper — botda allaqachon ishlatilayotgan xizmat) orqali matnga
   o'giriladi. So'z soni 4 tadan kam yoki 22 tadan ko'p bo'lgan bo'laklar
   chiqarib tashlanadi (juda qisqa/murakkab — shadowing uchun mos emas).
5. Qolgan bo'laklar shadowing_data/audio/ papkasiga Telegram voice uchun
   eng mos format — .ogg (Opus) sifatida saqlanadi, metama'lumotlari esa
   shadowing_data/manifest.json fayliga qo'shiladi (skript qayta ishga
   tushirilsa, mavjud kutubxona ustiga QO'SHILADI, o'chirilmaydi).

MUHIM — litsenziya va manba tanlash:
SOURCES ro'yxatiga faqat ta'lim maqsadida ochiq qo'yilgan yoki Creative
Commons / Public Domain materiallarni qo'shing:
  - VOA Learning English (learningenglish.voanews.com) — YouTube kanalidagi
    alohida dars videolari
  - BBC Learning English (youtube.com/@bbclearningenglish) — 6 Minute
    English va shunga o'xshash darslar
  - LibriVox (librivox.org) — Public Domain audiokitoblar
Har doim SOURCES ichida "url" maydoniga ALOHIDA EPIZOD/DARS havolasini
(masalan bitta YouTube video) qo'ying — dastur ro'yxati sahifasini emas.
Tasodifiy topilgan mualliflik huquqi bilan himoyalangan (film, musiqa,
yangilik agentligi eksklyuziv kontenti) materiallarni QO'SHMANG.
"""
import asyncio
import json
import re
import uuid
from pathlib import Path

from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import yt_dlp

from transcriber import transcribe_audio

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "shadowing_data"
AUDIO_DIR = DATA_DIR / "audio"
MANIFEST_PATH = DATA_DIR / "manifest.json"
TMP_DIR = DATA_DIR / "_tmp"

MIN_DURATION_MS = 3500
MAX_DURATION_MS = 8500
MIN_WORDS = 4
MAX_WORDS = 22
SILENCE_THRESH_OFFSET_DB = 16     # o'rtacha ovoz balandligidan necha dB past = sukunat
MIN_SILENCE_LEN_MS = 350

SOURCES_JSON_PATH = DATA_DIR / "sources.json"

# --- Manbalar ro'yxati: har biriga ALOHIDA EPIZOD havolasini yozing ---
# Eng qulay yo'l: shadowing_data/sources.json faylini tahrirlash (bu
# yerdagi SOURCES ro'yxatini ochish shart emas). Agar sources.json mavjud
# bo'lmasa, quyidagi bo'sh ro'yxat ishlatiladi (namuna uchun izohga olingan).
def _load_sources() -> list[dict]:
    if SOURCES_JSON_PATH.exists():
        return json.loads(SOURCES_JSON_PATH.read_text(encoding="utf-8"))
    return [
        # {
        #     "name": "VOA Learning English - Health & Lifestyle",
        #     "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
        #     "level": "easy",
        # },
        # {
        #     "name": "BBC 6 Minute English - Episode",
        #     "url": "https://www.youtube.com/watch?v=YYYYYYYYYYY",
        #     "level": "medium",
        # },
    ]


SOURCES = _load_sources()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:40]


def download_audio(url: str, out_stub: Path) -> Path:
    """Berilgan havoladan audio yuklab, mp3 sifatida saqlaydi va yo'lini
    qaytaradi. yt-dlp YouTube va ko'pgina to'g'ridan-to'g'ri media
    havolalarini (mp3/mp4 va h.k.) qo'llab-quvvatlaydi."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_stub) + ".%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    return out_stub.with_suffix(".mp3")


def slice_by_silence(audio_path: Path) -> list[AudioSegment]:
    """Audioni sukunat joylari bo'yicha bo'laklarga ajratadi — shu tarzda
    gaplar o'rtadan uzilib qolmaydi (tabiiy jumla chegaralarida kesiladi)."""
    audio = AudioSegment.from_file(audio_path)
    silence_thresh = audio.dBFS - SILENCE_THRESH_OFFSET_DB
    nonsilent_ranges = detect_nonsilent(
        audio, min_silence_len=MIN_SILENCE_LEN_MS, silence_thresh=silence_thresh
    )

    chunks = []
    for start, end in nonsilent_ranges:
        duration = end - start
        if duration < MIN_DURATION_MS:
            continue
        if duration <= MAX_DURATION_MS:
            chunks.append(audio[start:end])
        else:
            # Juda uzun bo'lakni (masalan uzoq pauzasiz nutq) taxminan
            # MAX_DURATION_MS bo'laklarga bo'lib tashlaymiz.
            pos = start
            while pos < end:
                piece_end = min(pos + MAX_DURATION_MS, end)
                if piece_end - pos >= MIN_DURATION_MS:
                    chunks.append(audio[pos:piece_end])
                pos = piece_end
    return chunks


async def build():
    if not SOURCES:
        print(
            "⚠️  Manbalar ro'yxati bo'sh. shadowing_data/sources.json "
            "faylini yarating (yoki to'ldiring) va o'zingiz tanlagan ochiq "
            "manba havolalarini qo'shing (har biri alohida video/audio "
            "epizod havolasi bo'lishi kerak). Namuna uchun "
            "shadowing_data/sources.example.json fayliga qarang."
        )
        return

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for source in SOURCES:
        print(f"\n=== {source['name']} ===")
        raw_stub = TMP_DIR / _slugify(source["name"])
        try:
            mp3_path = download_audio(source["url"], raw_stub)
        except Exception as e:
            print(f"  ⚠️  Yuklab olishda xatolik: {e}")
            continue

        chunks = slice_by_silence(mp3_path)
        print(f"  {len(chunks)} ta nomzod segment topildi, tekshirilmoqda...")

        accepted = 0
        for chunk in chunks:
            seg_id = str(uuid.uuid4())[:8]
            tmp_ogg = TMP_DIR / f"{seg_id}.ogg"
            chunk.export(tmp_ogg, format="ogg", codec="libopus")

            try:
                metrics = await transcribe_audio(str(tmp_ogg), language="en")
            except Exception as e:
                print(f"  ⚠️  Transkripsiyada xatolik: {e}")
                tmp_ogg.unlink(missing_ok=True)
                continue

            word_count = len(metrics.text.split())
            if not (MIN_WORDS <= word_count <= MAX_WORDS):
                tmp_ogg.unlink(missing_ok=True)
                continue

            final_path = AUDIO_DIR / f"{seg_id}.ogg"
            tmp_ogg.rename(final_path)

            manifest.append({
                "id": seg_id,
                "source": source["name"],
                "source_url": source["url"],
                "audio_path": str(final_path.relative_to(BASE_DIR)),
                "text": metrics.text.strip(),
                "duration_sec": round(len(chunk) / 1000, 2),
                "word_count": word_count,
                "level": source["level"],
            })
            accepted += 1

        print(f"  ✅ {accepted} ta segment kutubxonaga qo'shildi.")
        mp3_path.unlink(missing_ok=True)

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nJami kutubxonada: {len(manifest)} ta segment.")
    print(f"Manifest saqlandi: {MANIFEST_PATH}")


if __name__ == "__main__":
    asyncio.run(build())
