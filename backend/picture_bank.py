"""
Part 1.2 uchun tasodifiy surat juftlarini Unsplash'ning BEPUL API'si orqali
dinamik olish. (Foydalanuvchining ishlab turgan Speaking botidan olingan,
o'zgarishsiz.)
"""
import random

import aiohttp

from config import UNSPLASH_ACCESS_KEY

UNSPLASH_RANDOM_URL = "https://api.unsplash.com/photos/random"

THEME_PAIRS = [
    ("one man sitting alone armchair reading book at home",
     "group of friends playing football outdoors on field",
     ["What do you see in these pictures?",
      "Would you prefer to stay alone or with other people?",
      "Do you remember a time when you needed to cooperate with others?"]),
    ("family eating dinner together at home dining table",
     "people eating street food outdoors at food stall",
     ["What do you see in these pictures?",
      "Do you prefer eating at home or eating out?",
      "Describe a memorable meal you had outside your home."]),
    ("one person watching television alone on sofa at home",
     "group of friends playing football together outdoors",
     ["What do you see in these pictures?",
      "Do you prefer relaxing at home or being active with friends?",
      "Talk about a sport or game you enjoy playing with friends."]),
    ("one person cooking alone in kitchen at home",
     "large family gathering eating dinner together at table",
     ["What do you see in these pictures?",
      "Do you prefer eating alone or with your family?",
      "Describe a memorable meal you had with your family."]),
    ("one person working on laptop alone in home office",
     "group of colleagues in team meeting around table in office",
     ["What do you see in these pictures?",
      "Do you prefer working alone or in a team?",
      "Tell me about a time you worked successfully in a team."]),
    ("one person walking alone on forest trail in nature",
     "group of friends hiking together on mountain trail",
     ["What do you see in these pictures?",
      "Do you enjoy spending time in nature alone or with friends?",
      "Describe an outdoor activity you enjoyed with friends."]),
    ("one student studying alone at desk in library",
     "group of students working together on project at table",
     ["What do you see in these pictures?",
      "Do you study better alone or in a group?",
      "Talk about a group project you worked on."]),
    ("one person jogging alone on city street in morning",
     "group of people in fitness class exercising together in gym",
     ["What do you see in these pictures?",
      "Do you prefer exercising alone or in a group?",
      "Talk about your exercise routine."]),
    ("one person watering plants alone in home garden",
     "group of volunteers working together in community garden",
     ["What do you see in these pictures?",
      "Would you enjoy gardening alone or with a group of people?",
      "Describe a hobby you enjoy doing outdoors."]),
    ("one commuter sitting alone on train looking out window",
     "group of friends sitting together inside car on road trip",
     ["What do you see in these pictures?",
      "How do you usually travel to work or school?",
      "Describe a memorable journey you took with other people."]),
    ("one person playing video game alone at home with controller",
     "family playing board game together at table",
     ["What do you see in these pictures?",
      "Do you prefer playing games alone or with others?",
      "Describe a game you enjoy playing with family or friends."]),
    ("solo traveler with backpack walking alone in mountains",
     "group of tourists taking photo together in city square",
     ["What do you see in these pictures?",
      "Would you prefer to travel alone or in a group?",
      "Describe a trip you took with other people."]),
    ("one person sitting alone at restaurant table eating",
     "group of friends laughing together at dinner party table",
     ["What do you see in these pictures?",
      "Do you enjoy eating out alone or with friends?",
      "Describe a memorable dinner with friends or family."]),
    ("one person doing yoga alone at home",
     "group of people in yoga class together in studio",
     ["What do you see in these pictures?",
      "Do you prefer individual or group exercise classes?",
      "Talk about a fitness activity you have tried."]),
    ("one person fishing alone by lake",
     "group of friends having picnic together in park",
     ["What do you see in these pictures?",
      "How do you like to spend your free time outdoors?",
      "Describe a memorable day out with friends or family."]),
    ("one person shopping alone in clothing store",
     "group of friends shopping together laughing in mall",
     ["What do you see in these pictures?",
      "Do you prefer shopping alone or with friends?",
      "Describe your last shopping experience."]),
    ("one person camping alone in tent in forest",
     "group of friends sitting around campfire together at night",
     ["What do you see in these pictures?",
      "Would you rather go camping alone or with friends?",
      "Describe an outdoor trip you remember well."]),
]


async def _fetch_unsplash_photo(session: aiohttp.ClientSession, query: str) -> str:
    params = {
        "query": query,
        "client_id": UNSPLASH_ACCESS_KEY,
        "orientation": "landscape",
        "content_filter": "high",
    }
    async with session.get(UNSPLASH_RANDOM_URL, params=params, timeout=15) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data["urls"]["regular"]


async def get_random_picture_pair() -> dict:
    if not UNSPLASH_ACCESS_KEY:
        raise RuntimeError(
            "UNSPLASH_ACCESS_KEY sozlanmagan. Render Environment Variables'ga qo'shing "
            "(https://unsplash.com/developers dan bepul oling)."
        )

    query1, query2, questions = random.choice(THEME_PAIRS)

    async with aiohttp.ClientSession() as session:
        image1_url = await _fetch_unsplash_photo(session, query1)
        image2_url = await _fetch_unsplash_photo(session, query2)

    return {"image1_url": image1_url, "image2_url": image2_url, "questions": questions}
