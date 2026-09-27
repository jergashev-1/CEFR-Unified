# -*- coding: utf-8 -*-
"""
Speaking bot uchun Supabase (Postgres) bazasi.

Saqlanadigan ma'lumotlar:
  - speaking_users     : foydalanuvchi profili, referal va streak ma'lumotlari
  - speaking_results   : har bir baholash natijasi (reyting uchun ham ishlatiladi)
  - speaking_achievements : erishilgan yutuqlar (sertifikat berish uchun)

Writing botdagi bazaning AYNAN O'ZIDAN foydalaniladi (bitta DATABASE_URL),
lekin jadval nomlari "speaking_" prefiksi bilan boshlangani uchun Writing
botning "results" jadvaliga hech qanday ta'sir qilmaydi.
"""
import os
from datetime import date, timedelta

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL topilmadi. Render Environment Variables'ga "
                "Supabase ulanish manzilini qo'shing."
            )
        # statement_cache_size=0 — Supabase'ning "Transaction pooler" (pgbouncer)
        # bilan ishlash uchun zarur.
        _pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=1, max_size=5, statement_cache_size=0
        )
    return _pool


async def init_db():
    """Kerakli jadvallarni (agar mavjud bo'lmasa) yaratadi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_users (
                user_id BIGINT PRIMARY KEY,
                user_name TEXT,
                username TEXT,
                referred_by BIGINT,
                referral_count INT DEFAULT 0,
                current_streak INT DEFAULT 0,
                longest_streak INT DEFAULT 0,
                last_activity_date DATE,
                joined_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                user_name TEXT,
                part TEXT NOT NULL,
                score INT NOT NULL,
                max_score INT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_achievements (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                achievement_key TEXT NOT NULL,
                earned_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE (user_id, achievement_key)
            )
            """
        )


# ---------------------------------------------------------------------------
# FOYDALANUVCHI va REFERAL
# ---------------------------------------------------------------------------
async def register_user(user_id: int, user_name: str, username: str | None,
                        referred_by: int | None = None) -> dict:
    """Foydalanuvchini bazaga yozadi (agar yangi bo'lsa). Referal berilgan va
    foydalanuvchi haqiqatan yangi bo'lsa, taklif qiluvchining hisobini oshiradi.

    :return: {"is_new": bool, "referral_applied": bool}
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT user_id FROM speaking_users WHERE user_id = $1", user_id
        )
        if existing:
            # Ismi o'zgargan bo'lishi mumkin — yangilab qo'yamiz
            await conn.execute(
                "UPDATE speaking_users SET user_name = $2, username = $3 WHERE user_id = $1",
                user_id, user_name, username,
            )
            return {"is_new": False, "referral_applied": False}

        # O'zini o'zi taklif qilishga yo'l qo'ymaymiz
        valid_referrer = None
        if referred_by and referred_by != user_id:
            referrer = await conn.fetchrow(
                "SELECT user_id FROM speaking_users WHERE user_id = $1", referred_by
            )
            if referrer:
                valid_referrer = referred_by

        await conn.execute(
            """
            INSERT INTO speaking_users (user_id, user_name, username, referred_by)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, user_name, username, valid_referrer,
        )

        if valid_referrer:
            await conn.execute(
                "UPDATE speaking_users SET referral_count = referral_count + 1 WHERE user_id = $1",
                valid_referrer,
            )

        return {"is_new": True, "referral_applied": bool(valid_referrer)}


async def get_user(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM speaking_users WHERE user_id = $1", user_id)
    return dict(row) if row else None


async def get_referral_stats(user_id: int) -> dict:
    """Foydalanuvchining referal statistikasi va taklif qilganlari ro'yxati."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM speaking_users WHERE referred_by = $1", user_id
        )
        invited = await conn.fetch(
            """
            SELECT user_name, joined_at FROM speaking_users
            WHERE referred_by = $1 ORDER BY joined_at DESC LIMIT 10
            """,
            user_id,
        )
    return {"count": count or 0, "invited": [dict(r) for r in invited]}


async def get_referral_leaderboard(limit: int = 10) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_name, referral_count FROM speaking_users
            WHERE referral_count > 0
            ORDER BY referral_count DESC, joined_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# STREAK (ketma-ket kunlar)
# ---------------------------------------------------------------------------
async def update_streak(user_id: int) -> dict:
    """Foydalanuvchi faoliyat ko'rsatganda chaqiriladi. Streak'ni yangilaydi.

    :return: {"current_streak": int, "longest_streak": int, "is_new_day": bool,
              "streak_broken": bool}
    """
    pool = await get_pool()
    today = date.today()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT current_streak, longest_streak, last_activity_date FROM speaking_users WHERE user_id = $1",
            user_id,
        )
        if not row:
            return {"current_streak": 0, "longest_streak": 0, "is_new_day": False, "streak_broken": False}

        last_date = row["last_activity_date"]
        current = row["current_streak"] or 0
        longest = row["longest_streak"] or 0

        if last_date == today:
            # Bugun allaqachon hisobga olingan
            return {"current_streak": current, "longest_streak": longest,
                    "is_new_day": False, "streak_broken": False}

        streak_broken = False
        if last_date == today - timedelta(days=1):
            current += 1          # ketma-ketlik davom etmoqda
        elif last_date is None:
            current = 1           # birinchi marta
        else:
            current = 1           # uzilgan, qaytadan boshlanadi
            streak_broken = True

        longest = max(longest, current)

        await conn.execute(
            """
            UPDATE speaking_users
            SET current_streak = $2, longest_streak = $3, last_activity_date = $4
            WHERE user_id = $1
            """,
            user_id, current, longest, today,
        )

    return {"current_streak": current, "longest_streak": longest,
            "is_new_day": True, "streak_broken": streak_broken}


async def get_streak_leaderboard(limit: int = 10) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_name, current_streak, longest_streak FROM speaking_users
            WHERE current_streak > 0
            ORDER BY current_streak DESC, longest_streak DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# NATIJALAR va HAFTALIK REYTING
# ---------------------------------------------------------------------------
async def save_result(user_id: int, user_name: str, part: str, score: int, max_score: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO speaking_results (user_id, user_name, part, score, max_score)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id, user_name, part, score, max_score,
        )


async def get_weekly_leaderboard(limit: int = 10) -> list:
    """Oxirgi 7 kun ichidagi eng yaxshi natijalar (foydalanuvchi bo'yicha
    o'rtacha foiz, kamida 2 ta urinish qilganlar orasida)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_name,
                   COUNT(*) AS attempts,
                   ROUND(AVG(score::numeric / NULLIF(max_score, 0)) * 100) AS avg_percent
            FROM speaking_results
            WHERE created_at >= now() - interval '7 days'
            GROUP BY user_id, user_name
            HAVING COUNT(*) >= 2
            ORDER BY avg_percent DESC, attempts DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# YUTUQLAR (achievements)
# ---------------------------------------------------------------------------
async def grant_achievement(user_id: int, achievement_key: str) -> bool:
    """Yutuqni beradi. Agar allaqachon berilgan bo'lsa, False qaytaradi
    (shunda bot takroran tabriklamaydi)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            INSERT INTO speaking_achievements (user_id, achievement_key)
            VALUES ($1, $2)
            ON CONFLICT (user_id, achievement_key) DO NOTHING
            """,
            user_id, achievement_key,
        )
    return result.endswith("1")  # "INSERT 0 1" -> yangi qo'shildi


async def get_achievements(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT achievement_key, earned_at FROM speaking_achievements WHERE user_id = $1 ORDER BY earned_at",
            user_id,
        )
    return [dict(r) for r in rows]
