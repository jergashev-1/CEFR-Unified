# -*- coding: utf-8 -*-
"""
Sotiladigan materiallar (handout/worksheet) katalogi.

Ikki xil to'lov usuli qo'llab-quvvatlanadi (har bir mahsulot uchun alohida
tanlanadi, "payment_method" maydoni orqali):

  "stars" — Telegram Stars orqali, TO'LIQ AVTOMATIK:
      foydalanuvchi to'laydi -> bot darhol PDF faylni yuboradi.
      Ro'yxatdan o'tish yoki tasdiqlash kerak emas.

  "card"  — Bank kartasi orqali, YARIM AVTOMATIK:
      foydalanuvchiga narx (so'mda) va karta raqami ko'rsatiladi ->
      foydalanuvchi pulni o'tkazadi -> to'lov chekining skrinshotini
      botga yuboradi -> bot screenshot'ni ADMINGA yuboradi -> admin
      "✅ Tasdiqlash" tugmasini bosgach, bot avtomatik ravishda
      foydalanuvchiga PDF faylni yuboradi.

YANGI MAHSULOT QO'SHISH UCHUN:
  1. PDF faylni ushbu botning repo'sidagi `materials/` papkasiga joylang.
  2. Quyidagi PRODUCTS lug'atiga yangi element qo'shing (pastdagi ikkita
     namunadan birini asos qilib oling — "stars" yoki "card").
  3. Agar mahsulot ikkala botda ham sotilishi kerak bo'lsa, xuddi shu PDF
     faylni HAR IKKALA bot repo'siga alohida joylashtiring (ular alohida
     GitHub repolari bo'lgani uchun) va shu faylni ham ikkalasiga qo'shing.
"""
import os

MATERIALS_DIR = "materials"

PRODUCTS = {
    # --- STARS orqali sotiladigan mahsulot namunasi ---
    # "b1_informal_letter_pack": {
    #     "title": "B1 Writing — Norasmiy xat shabloni to'plami",
    #     "description": "10 ta tayyor namuna va 15 ta mashq bilan PDF qo'llanma.",
    #     "payment_method": "stars",
    #     "price_stars": 50,
    #     "filename": "b1_informal_letter_pack.pdf",
    # },

    # --- Karta (so'm) orqali sotiladigan mahsulot namunasi ---
    # "speaking_part3_topics": {
    #     "title": "Speaking Part 3 — 50 ta mavzu va namunaviy javoblar",
    #     "description": "B2/C1 darajasidagi 50 ta mavzu, har biriga namunaviy javob tuzilmasi.",
    #     "payment_method": "card",
    #     "price_display": "25 000 so'm",
    #     "filename": "speaking_part3_topics.pdf",
    # },
}


def get_material_path(filename: str) -> str:
    return os.path.join(MATERIALS_DIR, filename)


def _price_label(product: dict) -> str:
    if product.get("payment_method") == "card":
        return product.get("price_display", "narx ko'rsatilmagan")
    return f"{product.get('price_stars', '?')}⭐"


def build_shop_keyboard():
    """Mavjud mahsulotlar ro'yxatini InlineKeyboardMarkup sifatida qaytaradi."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(
            text=f"{p['title']} — {_price_label(p)}",
            callback_data=f"buy:{pid}",
        )]
        for pid, p in PRODUCTS.items()
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Yopish", callback_data="shop_close")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_admin_approval_kb(user_id: int, product_id: str):
    """Admin uchun: karta orqali to'lovni tasdiqlash/rad etish tugmalari."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_order:{user_id}:{product_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_order:{user_id}:{product_id}"),
    ]])
