"""
4 ta qism (Part 1.1, 1.2, 2, 3) xom ballarini birlashtirib, rasmiy DTM/UZBMB
tizimidagi 0-75 ballik shkalaga TAXMINIY aylantirish.

MUHIM CHEKLOV: Rasmiy imtihonda xom 0-21 jami maxsus statistik model
(Rasch/CMLE) asosidagi konvertatsiya jadvali orqali 0-75 ballga
aylantiriladi. Bu jadval ochiq e'lon qilinmagan, shuning uchun bu yerda
oddiy PROPORSIONAL (chiziqli) formula ishlatiladi — bu rasmiy emas, faqat
taxminiy yo'nalish beradi. Daraja chegaralari esa rasmiy manbalarga mos:
C1 65-75, B2 51-64, B1 38-50, A2 20-37, A1 0-19.
"""

MAX_RAW_SCORES = {"1.1": 5, "1.2": 5, "2": 5, "3": 6}
MAX_RAW_TOTAL = sum(MAX_RAW_SCORES.values())  # 21
MAX_SCALED = 75

BAND_THRESHOLDS = [
    (65, 75, "C1"),
    (51, 64, "B2"),
    (38, 50, "B1"),
    (20, 37, "A2"),
    (0, 19, "A1"),
]


def scaled_score_to_band(scaled_score: int) -> str:
    for low, high, band in BAND_THRESHOLDS:
        if low <= scaled_score <= high:
            return band
    return "A1"


def compute_overall(raw_scores: dict) -> dict | None:
    """
    :param raw_scores: {"1.1": int, "1.2": int, "2": int, "3": int} —
        har bir qism bo'yicha eng so'nggi xom ball
    :return: None agar biror qism yetishmasa, aks holda:
        {"raw_total": int, "max_raw_total": int, "scaled_score": int,
         "band": str}
    """
    missing = [p for p in MAX_RAW_SCORES if p not in raw_scores]
    if missing:
        return None

    raw_total = sum(raw_scores[p] for p in MAX_RAW_SCORES)
    scaled = round(raw_total / MAX_RAW_TOTAL * MAX_SCALED)
    scaled = max(0, min(MAX_SCALED, scaled))
    band = scaled_score_to_band(scaled)

    return {
        "raw_total": raw_total,
        "max_raw_total": MAX_RAW_TOTAL,
        "scaled_score": scaled,
        "band": band,
    }
