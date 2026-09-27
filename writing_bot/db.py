# -*- coding: utf-8 -*-
"""
Supabase (Postgres) bazasida foydalanuvchi natijalarini doimiy saqlash.
Bu bot qayta ishga tushsa ham (Render bepul tarifi, redeploy va h.k.)
natijalar yo'qolib ketmasligini ta'minlaydi.
"""
import os

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL topilmadi. .env fayliga Supabase ulanish manzilini qo'shing."
            )
        # statement_cache_size=0 — Supabase'ning "Transaction pooler" (pgbouncer)
        # bilan ishlash uchun zarur, aks holda xatolik berishi mumkin.
        _pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=1, max_size=5, statement_cache_size=0
        )
    return _pool


async def init_db():
    """Kerakli jadvalni (agar mavjud bo'lmasa) yaratadi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                user_name TEXT,
                task_key TEXT NOT NULL,
                score INT NOT NULL,
                max_score INT NOT NULL,
                estimated_level TEXT,
                comment TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        # "Qayta urinish" tugmasi uchun oxirgi (hali baholanmagan yoki xatolik
        # bergan) topshiriqni saqlaydi. RAM o'rniga bazada saqlanadi, shunda
        # Render qayta ishga tushsa/uxlab qolsa ham foydalanuvchi matni
        # yo'qolmaydi. Har bir user_id uchun faqat bitta (eng oxirgi) yozuv
        # saqlanadi — shu sababli user_id PRIMARY KEY va UPSERT ishlatiladi.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_submissions (
                user_id BIGINT PRIMARY KEY,
                task_key TEXT NOT NULL,
                text TEXT NOT NULL,
                task_prompt TEXT,
                timed BOOLEAN DEFAULT FALSE,
                start_time TEXT,
                time_limit INT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )


async def save_result(
    user_id: int, user_name: str, task_key: str, score: int,
    max_score: int, estimated_level: str, comment: str,
):
    """Yangi baholash natijasini bazaga yozadi (eskisini o'chirmaydi — tarix saqlanadi)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO results (user_id, user_name, task_key, score, max_score, estimated_level, comment)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            user_id, user_name, task_key, score, max_score, estimated_level, comment,
        )


async def get_latest_results(user_id: int) -> dict:
    """Har bir task_key uchun eng oxirgi natijani qaytaradi: {task_key: {...}}"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (task_key) task_key, score, max_score, estimated_level, created_at
            FROM results
            WHERE user_id = $1
            ORDER BY task_key, created_at DESC
            """,
            user_id,
        )
    return {row["task_key"]: dict(row) for row in rows}


async def get_history(user_id: int, limit: int = 20) -> list:
    """Foydalanuvchining oxirgi urinishlari tarixini qaytaradi (eng yangisi birinchi)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT task_key, score, max_score, estimated_level, created_at
            FROM results
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id, limit,
        )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# "Qayta urinish" uchun kutilayotgan (baholanmagan) topshiriqlar
# ---------------------------------------------------------------------------

async def save_pending_submission(
    user_id: int, task_key: str, text: str, task_prompt: str | None = None,
    timed: bool = False, start_time: str | None = None, time_limit: int | None = None,
):
    """Baholash muvaffaqiyatsiz bo'lganda (yoki hali baholanmagan) matnni
    saqlaydi, shunda 'Qayta urinish' tugmasi bot qayta ishga tushgandan
    keyin ham ishlaydi. Har bir user_id uchun faqat bitta yozuv bo'ladi —
    eskisi UPSERT orqali yangisi bilan almashtiriladi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pending_submissions
                (user_id, task_key, text, task_prompt, timed, start_time, time_limit, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, now())
            ON CONFLICT (user_id) DO UPDATE SET
                task_key = EXCLUDED.task_key,
                text = EXCLUDED.text,
                task_prompt = EXCLUDED.task_prompt,
                timed = EXCLUDED.timed,
                start_time = EXCLUDED.start_time,
                time_limit = EXCLUDED.time_limit,
                created_at = now()
            """,
            user_id, task_key, text, task_prompt, timed, start_time, time_limit,
        )


async def get_pending_submission(user_id: int) -> dict | None:
    """Foydalanuvchining saqlangan (hali baholanmagan) oxirgi topshiriqni
    qaytaradi, mavjud bo'lmasa None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pending_submissions WHERE user_id = $1",
            user_id,
        )
    return dict(row) if row else None


async def delete_pending_submission(user_id: int):
    """Baholash muvaffaqiyatli yakunlangach, saqlangan yozuvni tozalaydi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM pending_submissions WHERE user_id = $1",
            user_id,
        )
