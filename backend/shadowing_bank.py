# -*- coding: utf-8 -*-
"""
Shadowing mashqi uchun CEFR darajalar bo'yicha jumlalar banki.
Har bir daraja o'tgan darajadan uzunroq/murakkabroq jumlalarni o'z ichiga
oladi — bu talaffuz, ravonlik va nafas olish tartibini progressiv ravishda
mashq qilish uchun mo'ljallangan (shadowing texnikasi).
"""
import random

SHADOWING_SENTENCES = {
    "A2": [
        "I usually wake up early in the morning.",
        "She likes to drink coffee with her breakfast.",
        "We are going to the market this afternoon.",
        "He works in a small office near his house.",
        "My brother plays football every weekend.",
        "The weather is really nice today.",
        "They live in a small flat in the city center.",
        "I need to buy some milk and bread.",
        "Can you help me find the train station?",
        "She always arrives at school on time.",
        "We watched a funny movie last night.",
        "He doesn't like spicy food very much.",
        "I am learning English because I want to travel.",
        "The children are playing in the garden.",
        "My favorite season is summer because it's warm.",
    ],
    "B1": [
        "Although it was raining heavily, we decided to go for a walk anyway.",
        "I've been trying to learn how to cook traditional dishes from my grandmother.",
        "She was really nervous before the interview, but everything went well in the end.",
        "If I had more free time, I would probably start learning a new language.",
        "We're planning to visit several cities during our trip next summer.",
        "He mentioned that he might be moving to a different city for work.",
        "It took me a while to get used to the new schedule at my job.",
        "Even though the movie got great reviews, I didn't really enjoy it.",
        "They've recently opened a new restaurant just around the corner from here.",
        "I was surprised to hear that she had already finished the whole project.",
        "Since I started exercising regularly, I've noticed a big difference in my energy levels.",
        "We should probably book the tickets soon before the prices go up.",
    ],
    "B2": [
        "Despite having very little experience in the field, she managed to impress everyone during the presentation.",
        "The government has announced a series of measures aimed at reducing traffic congestion in major cities.",
        "One of the biggest challenges we face is convincing people to change their daily habits for the environment.",
        "Although the results were somewhat disappointing, the research team remained optimistic about future developments.",
        "It's becoming increasingly difficult for small businesses to compete with large international corporations.",
        "The committee is currently reviewing several proposals before making a final decision next month.",
        "What struck me most about the documentary was how differently people perceive the same historical event.",
        "As technology continues to evolve, many traditional jobs are being replaced by automated systems.",
        "She had to completely rethink her approach after realizing the original plan simply wouldn't work.",
        "Critics have argued that the new policy fails to address the root causes of the problem.",
    ],
    "C1": [
        "Notwithstanding the considerable advances made in renewable energy, fossil fuels remain the dominant source of power worldwide.",
        "The extent to which social media has reshaped public discourse is a subject of ongoing debate among scholars.",
        "Had the negotiations been handled with greater diplomatic sensitivity, the outcome might have been entirely different.",
        "It is not so much the lack of resources as the absence of coordinated strategy that has hindered progress.",
        "The sheer complexity of the global supply chain makes it exceedingly difficult to pinpoint the source of the disruption.",
        "While proponents argue that the reform will stimulate growth, skeptics remain unconvinced of its long-term viability.",
        "Rarely has a single innovation had such a profound and far-reaching impact on the way we communicate.",
        "The nuanced interplay between cultural identity and economic policy often eludes straightforward analysis.",
        "Only by acknowledging the shortcomings of the previous system can meaningful reform be achieved.",
        "The implications of this discovery extend far beyond the narrow confines of the laboratory.",
    ],
}

LEVEL_ORDER = ["A2", "B1", "B2", "C1"]


def get_random_sentence(level: str) -> dict:
    """Berilgan daraja uchun tasodifiy jumla qaytaradi."""
    if level not in SHADOWING_SENTENCES:
        level = "A2"
    sentence = random.choice(SHADOWING_SENTENCES[level])
    return {
        "level": level,
        "text": sentence,
        "word_count": len(sentence.split()),
    }


def get_next_level(current_level: str) -> str | None:
    """Keyingi darajani qaytaradi, agar eng yuqori daraja bo'lsa None qaytaradi."""
    try:
        idx = LEVEL_ORDER.index(current_level)
    except ValueError:
        return "A2"
    if idx + 1 < len(LEVEL_ORDER):
        return LEVEL_ORDER[idx + 1]
    return None
