# -*- coding: utf-8 -*-
"""
"Fikr banki" posti uchun mavzular bazasi (90 ta).

Bu mavzular Speaking Part 3 ("For/Against" munozara) va Writing Task 2
(essay/blog post) bilan BIR XIL domenlardan tanlangan — ya'ni foydalanuvchi
kanalda o'qigan fikr-argumentlarini keyinchalik haqiqiy Speaking va Writing
testlarida ham ishlata oladi. Mavzular quyidagi kengroq sohalarni qamrab
oladi: ta'lim, texnologiya, atrof-muhit, sog'liq, ijtimoiy tarmoq/media,
ish/iqtisodiyot, davlat siyosati, madaniyat, transport, sayohat va h.k.

AI shu ro'yxatdan tasodifiy tanlangan ANIQ mavzu ustida ishlaydi — o'zi
erkin mavzu tanlamaydi. Bu bir xil mavzularning tez-tez takrorlanishining
oldini oladi.
"""
import random

IDEA_BANK_TOPICS = [
    # Ta'lim
    "Standardized testing in schools",
    "Homeschooling vs traditional schooling",
    "University tuition fees",
    "Should homework be abolished",
    "Online learning vs classroom learning",
    "Gap year before university",
    "Should coding be taught in all schools",
    "Grading systems and student stress",
    "Bilingual education",
    "Should university education be free",

    # Texnologiya va sun'iy intellekt
    "Advantages of artificial intelligence",
    "Risks of artificial intelligence",
    "Social media's impact on society",
    "Screen time for children",
    "Self-driving cars",
    "Robots replacing human jobs",
    "Cryptocurrency and digital money",
    "Privacy and online surveillance",
    "Video games and violence",
    "Influencer culture",
    "Fake news and media literacy",
    "Space exploration and colonizing Mars",
    "Genetic engineering",
    "Wearable health technology",

    # Atrof-muhit
    "Climate change",
    "Plastic pollution",
    "Renewable energy sources",
    "Deforestation",
    "Overpopulation",
    "Water scarcity",
    "Wildlife conservation",
    "Fast fashion and its environmental impact",
    "Electric vehicles",
    "Nuclear energy",
    "Recycling programs",
    "Air pollution in big cities",

    # Sog'liq
    "Healthy lifestyle habits",
    "Fast food industry",
    "Mental health awareness",
    "Sleep deprivation in modern life",
    "Vaccination policies",
    "Alternative medicine",
    "Obesity epidemic",
    "Work-related stress",
    "Aging population and healthcare",
    "Organic food",

    # Jamiyat va ijtimoiy masalalar
    "Gender equality in the workplace",
    "Income inequality",
    "Immigration policies",
    "Freedom of speech",
    "Crime and punishment",
    "Poverty reduction",
    "Minimum wage",
    "Universal basic income",
    "Volunteer work",
    "Single-parent families",
    "Arranged marriage vs love marriage",
    "Traditional culture vs modernization",
    "Language extinction",
    "Cultural heritage preservation",
    "Animal rights",
    "Zoos and animal captivity",

    # Ish va iqtisodiyot
    "Remote work vs office work",
    "The four-day work week",
    "The gig economy and freelancing",
    "Corporate social responsibility",
    "Retirement age",
    "Advertising aimed at children",
    "Consumer debt and financial literacy",
    "Automation and the future of jobs",
    "Work-life balance",

    # Shahar, transport, sayohat
    "Public transport vs private cars",
    "Urbanization and city growth",
    "Tourism's impact on local communities",
    "Space tourism",
    "Traffic congestion solutions",
    "Living in a big city vs a small town",

    # Ta'lim va texnologiya kesishmasi
    "Should smartphones be banned in schools",
    "The role of libraries in the digital age",
    "E-books vs printed books",

    # Boshqa umumiy bahsli mavzular
    "Reality TV and its influence on society",
    "Beauty standards and social pressure",
    "Minimalism and consumer culture",
    "The importance of preserving endangered languages",
    "Should voting be mandatory",
    "The role of the government in personal life",
    "Globalization's effect on local businesses",
    "The importance of learning a second language",
    "Should zoos be replaced by wildlife sanctuaries",
    "The impact of tourism on historical sites",
]


def get_random_idea_topic() -> str:
    """Bankdan tasodifiy mavzu qaytaradi."""
    return random.choice(IDEA_BANK_TOPICS)
