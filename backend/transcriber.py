"""
Audio faylni matnga aylantirish (Speech-to-Text) — Groq'ning BEPUL
Whisper API'si orqali. (Foydalanuvchining ishlab turgan Speaking botidan
olingan, o'zgarishsiz.)
"""
import re
from dataclasses import dataclass, field

from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_WHISPER_MODEL

client = AsyncGroq(api_key=GROQ_API_KEY)

FILLER_WORDS = [
    "um", "uh", "umm", "uhh", "erm", "hmm",
    "like", "you know", "i mean", "sort of", "kind of", "well",
]


@dataclass
class AudioMetrics:
    text: str
    duration_sec: float = 0.0
    speaking_words_per_min: float = 0.0
    pause_count: int = 0
    total_pause_sec: float = 0.0
    longest_pause_sec: float = 0.0
    filler_count: int = 0
    filler_examples: list = field(default_factory=list)
    avg_logprob: float = 0.0
    avg_no_speech_prob: float = 0.0
    low_confidence_segment_count: int = 0

    def summary_uz(self) -> str:
        return (
            f"- Umumiy audio davomiyligi: {self.duration_sec:.1f} soniya\n"
            f"- Gapirish tezligi: {self.speaking_words_per_min:.0f} so'z/daqiqa\n"
            f"- Pauzalar (0.5s+): {self.pause_count} ta, jami {self.total_pause_sec:.1f}s, "
            f"eng uzuni {self.longest_pause_sec:.1f}s\n"
            f"- Filler/ikkilanish so'zlari ('um', 'uh', 'like' va h.k.): {self.filler_count} marta\n"
            f"- Whisper akustik ishonch darajasi (avg_logprob): {self.avg_logprob:.2f} "
            f"(0 ga yaqin = aniq eshitilgan, -1 dan past = noaniq/tushunarsiz)\n"
            f"- Nutqsiz/noaniq segmentlar ulushi: {self.avg_no_speech_prob*100:.0f}%\n"
            f"- Past ishonchli (ehtimol noaniq talaffuzli) segmentlar soni: "
            f"{self.low_confidence_segment_count}"
        )


async def transcribe_audio(file_path: str, language: str = "en") -> AudioMetrics:
    with open(file_path, "rb") as audio_file:
        result = await client.audio.transcriptions.create(
            model=GROQ_WHISPER_MODEL,
            file=audio_file,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments = getattr(result, "segments", None) or []
    text = getattr(result, "text", "") or ""

    metrics = AudioMetrics(text=text.strip())

    if segments:
        last_end = segments[-1]["end"] if isinstance(segments[-1], dict) else segments[-1].end
        metrics.duration_sec = float(last_end)

        word_count = len(text.split())
        if metrics.duration_sec > 0:
            metrics.speaking_words_per_min = word_count / (metrics.duration_sec / 60)

        pauses = []
        for i in range(1, len(segments)):
            prev = segments[i - 1]
            cur = segments[i]
            prev_end = prev["end"] if isinstance(prev, dict) else prev.end
            cur_start = cur["start"] if isinstance(cur, dict) else cur.start
            gap = float(cur_start) - float(prev_end)
            if gap >= 0.5:
                pauses.append(gap)

        metrics.pause_count = len(pauses)
        metrics.total_pause_sec = sum(pauses)
        metrics.longest_pause_sec = max(pauses) if pauses else 0.0

        logprobs = []
        no_speech_probs = []
        low_confidence_count = 0
        for seg in segments:
            lp = seg.get("avg_logprob") if isinstance(seg, dict) else getattr(seg, "avg_logprob", None)
            nsp = seg.get("no_speech_prob") if isinstance(seg, dict) else getattr(seg, "no_speech_prob", None)
            if lp is not None:
                logprobs.append(float(lp))
                if lp < -0.8:
                    low_confidence_count += 1
            if nsp is not None:
                no_speech_probs.append(float(nsp))

        metrics.avg_logprob = sum(logprobs) / len(logprobs) if logprobs else 0.0
        metrics.avg_no_speech_prob = (
            sum(no_speech_probs) / len(no_speech_probs) if no_speech_probs else 0.0
        )
        metrics.low_confidence_segment_count = low_confidence_count

    lowered = text.lower()
    found = []
    for fw in FILLER_WORDS:
        count = len(re.findall(rf"\b{re.escape(fw)}\b", lowered))
        if count:
            found.extend([fw] * count)
    metrics.filler_count = len(found)
    metrics.filler_examples = found[:5]

    return metrics
