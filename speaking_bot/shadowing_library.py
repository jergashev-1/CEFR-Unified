"""
Shadowing mashqlari uchun ochiq manbalardan tayyorlangan audio segmentlar
kutubxonasi.

Kutubxona oldindan `build_shadowing_library.py` skripti yordamida
tayyorlanadi: uzun audio (VOA Learning English, BBC Learning English,
LibriVox va h.k. kabi ochiq/ta'lim maqsadidagi manbalar) tabiiy pauzalar
bo'yicha 4-8 soniyalik segmentlarga bo'linadi va har biri uchun aniq
transkript (Whisper yordamida) saqlanadi.

Bot ishga tushganda faqat shu tayyor manifestni (JSON) o'qiydi — internetdan
"jonli" yuklab olish qilmaydi. Bu ham tezroq, ham xavfsizroq (nazoratsiz
manba runtime'da yuklanmaydi).
"""
import json
import random
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
MANIFEST_PATH = BASE_DIR / "shadowing_data" / "manifest.json"


@dataclass
class ShadowingSegment:
    id: str
    source: str            # masalan: "VOA Learning English - Health Report"
    source_url: str        # asl material havolasi (manba ko'rsatish uchun)
    audio_path: str        # lokal fayl yo'li (.ogg)
    text: str              # segmentning aniq transkripti
    duration_sec: float
    word_count: int
    level: str              # "easy" | "medium" | "hard"

    @property
    def expected_wpm(self) -> float:
        if self.duration_sec <= 0:
            return 0.0
        return self.word_count / (self.duration_sec / 60)

    @property
    def full_audio_path(self) -> str:
        p = Path(self.audio_path)
        if p.is_absolute():
            return str(p)
        return str(BASE_DIR / p)


_segments: list[ShadowingSegment] | None = None

# Eski kutubxonalarda "easy"/"medium"/"hard" kabi soddalashtirilgan
# darajalar bo'lishi mumkin — CEFR progressiyasi bilan mos ishlashi uchun
# ularni taxminiy CEFR darajalariga moslaymiz.
LEGACY_LEVEL_MAP = {"easy": "A2", "medium": "B1", "hard": "C1"}


def _normalize_level(level: str) -> str:
    return LEGACY_LEVEL_MAP.get(level, level)


def _load() -> list[ShadowingSegment]:
    global _segments
    if _segments is None:
        if not MANIFEST_PATH.exists():
            _segments = []
        else:
            raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            _segments = [ShadowingSegment(**item) for item in raw]
    return _segments


def reload_library() -> None:
    """Manifest yangilangandan keyin (masalan build skripti qayta ishga
    tushirilgandan so'ng) keshni tozalab, qayta o'qish uchun."""
    global _segments
    _segments = None


def get_random_segment(level: str | None = None) -> ShadowingSegment | None:
    segments = _load()
    if not segments:
        return None
    pool = [s for s in segments if level is None or _normalize_level(s.level) == level]
    if not pool:
        pool = segments
    return random.choice(pool)


def get_segment_by_id(segment_id: str) -> ShadowingSegment | None:
    for s in _load():
        if s.id == segment_id:
            return s
    return None


def library_size() -> int:
    return len(_load())
