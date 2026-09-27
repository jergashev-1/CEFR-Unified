# -*- coding: utf-8 -*-
"""
Ertalabki salomlashish posti uchun mavzu/burchak (angle) banki (45 ta).

AI'ga to'liq erkinlik berilganda, u tez-tez bir xil umumiy shablonga
("Good morning! Today is a new day...") qaytib qolishga moyil bo'ladi —
hatto yuqori "temperature" bilan ham. Shuning uchun har safar TASODIFIY
bitta aniq mavzu/burchak beriladi, AI esa faqat o'sha mavzu atrofida
yozadi. Bu haqiqiy xilma-xillikni kafolatlaydi.
"""
import random

MORNING_THEMES = [
    "small consistent steps leading to big progress",
    "the excitement of learning something new today",
    "gratitude for a fresh start",
    "curiosity as the engine of language learning",
    "celebrating yesterday's small wins",
    "the power of a positive first thought in the morning",
    "comparing language learning to planting a seed",
    "embracing mistakes as part of growth",
    "the quiet confidence that comes from daily practice",
    "turning a busy day into an opportunity to practice English",
    "the joy of understanding one new word today",
    "patience with yourself during the learning process",
    "the energy of a new week (if relevant) or a new day",
    "finding motivation in your own past progress",
    "the idea that consistency beats perfection",
    "morning coffee/tea as a moment to think in English",
    "believing in your future fluent self",
    "the adventure of exploring a new language",
    "resilience after a difficult day yesterday",
    "the simple discipline of showing up every day",
    "focusing on progress, not perfection",
    "the courage it takes to speak a new language",
    "using today's challenges as practice material",
    "the satisfaction of a well-spent morning",
    "building confidence one sentence at a time",
    "the connection between mindset and success",
    "treating language learning as a lifelong journey",
    "the value of community and learning together",
    "starting the day with intention and focus",
    "the beauty of ordinary days building extraordinary skills",
    "letting go of perfectionism to make real progress",
    "the quiet power of habit",
    "seeing setbacks as setups for comebacks",
    "the freedom that comes with expressing yourself in English",
    "how small daily efforts compound over time",
    "waking up with purpose",
    "the calm before a productive day",
    "trusting the process of learning",
    "finding joy in the little details of a new language",
    "the reminder that every expert was once a beginner",
    "using curiosity to turn boredom into learning",
    "a gentle reminder to be kind to yourself today",
    "the excitement of not knowing what new words you'll learn today",
    "channeling morning energy into meaningful practice",
    "the idea that today is a blank page waiting to be written",
]


def get_random_morning_theme() -> str:
    """Bankdan tasodifiy mavzu/burchak qaytaradi."""
    return random.choice(MORNING_THEMES)
