"""Thin async PostgreSQL repo (asyncpg, explicit SQL, no ORM).

A single global pool is created on startup and closed on shutdown. The schema
(`schema.sql`) is idempotent and run on every startup. Only durable data lives
here — the batch session stays in memory.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Path to the idempotent schema file (repo root).
_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "schema.sql")


class Database:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool not initialized")
        return self._pool

    async def connect(self, dsn: str) -> None:
        self._pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
        await self._run_schema()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def _run_schema(self) -> None:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
            sql = fh.read()
        # asyncpg's simple-query protocol runs multiple ';'-separated statements.
        await self.pool.execute(sql)
        logger.info("Schema applied")

    # --- Users -----------------------------------------------------------
    async def get_user(self, telegram_id: int) -> asyncpg.Record | None:
        return await self.pool.fetchrow("SELECT * FROM users WHERE telegram_id=$1", telegram_id)

    async def create_user(
        self,
        telegram_id: int,
        referral_code: str,
        bonus_audio_sec: int,
        bonus_photos: int,
        referred_by: int | None,
    ) -> asyncpg.Record | None:
        """Insert a user if absent. Returns the row, or None if it already existed."""
        return await self.pool.fetchrow(
            """
            INSERT INTO users (telegram_id, bonus_audio_sec, bonus_photos, referral_code, referred_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (telegram_id) DO NOTHING
            RETURNING *
            """,
            telegram_id, bonus_audio_sec, bonus_photos, referral_code, referred_by,
        )

    async def user_by_referral_code(self, code: str) -> asyncpg.Record | None:
        return await self.pool.fetchrow("SELECT * FROM users WHERE referral_code=$1", code)

    async def set_lang_override(self, telegram_id: int, lang: str) -> None:
        await self.pool.execute(
            "UPDATE users SET lang_override=$2 WHERE telegram_id=$1", telegram_id, lang
        )

    async def set_pro_until(self, telegram_id: int, until: dt.datetime) -> None:
        await self.pool.execute(
            "UPDATE users SET pro_until=$2 WHERE telegram_id=$1", telegram_id, until
        )

    async def set_byo_key(self, telegram_id: int, enc: str | None) -> None:
        await self.pool.execute(
            "UPDATE users SET byo_key_enc=$2 WHERE telegram_id=$1", telegram_id, enc
        )

    async def add_bonus(self, telegram_id: int, audio_sec: int, photos: int) -> None:
        await self.pool.execute(
            "UPDATE users SET bonus_audio_sec = bonus_audio_sec + $2, "
            "bonus_photos = bonus_photos + $3 WHERE telegram_id=$1",
            telegram_id, audio_sec, photos,
        )

    async def consume_bonus(self, telegram_id: int, audio_sec: int, photos: int) -> None:
        await self.pool.execute(
            "UPDATE users SET bonus_audio_sec = GREATEST(bonus_audio_sec - $2, 0), "
            "bonus_photos = GREATEST(bonus_photos - $3, 0) WHERE telegram_id=$1",
            telegram_id, audio_sec, photos,
        )

    # --- Daily usage -----------------------------------------------------
    async def get_usage(self, telegram_id: int, day: dt.date) -> asyncpg.Record | None:
        return await self.pool.fetchrow(
            "SELECT * FROM usage_daily WHERE telegram_id=$1 AND day=$2", telegram_id, day
        )

    async def incr_usage(
        self,
        telegram_id: int,
        day: dt.date,
        *,
        audio_sec: int = 0,
        photos: int = 0,
        llm_calls: int = 0,
        images: int = 0,
        pptx: int = 0,
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO usage_daily (telegram_id, day, audio_sec, photos, llm_calls, images, pptx)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (telegram_id, day) DO UPDATE SET
              audio_sec = usage_daily.audio_sec + EXCLUDED.audio_sec,
              photos    = usage_daily.photos    + EXCLUDED.photos,
              llm_calls = usage_daily.llm_calls + EXCLUDED.llm_calls,
              images    = usage_daily.images    + EXCLUDED.images,
              pptx      = usage_daily.pptx      + EXCLUDED.pptx
            """,
            telegram_id, day, audio_sec, photos, llm_calls, images, pptx,
        )

    # --- Media cache -----------------------------------------------------
    async def media_cache_get(self, file_unique_id: str) -> str | None:
        return await self.pool.fetchval(
            "SELECT text FROM media_cache WHERE file_unique_id=$1", file_unique_id
        )

    async def media_cache_put(self, file_unique_id: str, kind: str, text: str) -> None:
        await self.pool.execute(
            "INSERT INTO media_cache (file_unique_id, kind, text) VALUES ($1, $2, $3) "
            "ON CONFLICT (file_unique_id) DO NOTHING",
            file_unique_id, kind, text,
        )

    # --- Saved prompts ---------------------------------------------------
    async def prompts_list(self, telegram_id: int) -> list[asyncpg.Record]:
        return await self.pool.fetch(
            "SELECT * FROM saved_prompts WHERE telegram_id=$1 ORDER BY created_at DESC",
            telegram_id,
        )

    async def prompts_count(self, telegram_id: int) -> int:
        return await self.pool.fetchval(
            "SELECT count(*) FROM saved_prompts WHERE telegram_id=$1", telegram_id
        )

    async def prompt_get(self, prompt_id: int, telegram_id: int) -> asyncpg.Record | None:
        return await self.pool.fetchrow(
            "SELECT * FROM saved_prompts WHERE id=$1 AND telegram_id=$2", prompt_id, telegram_id
        )

    async def prompt_add(self, telegram_id: int, title: str, body: str) -> None:
        await self.pool.execute(
            "INSERT INTO saved_prompts (telegram_id, title, body) VALUES ($1, $2, $3)",
            telegram_id, title, body,
        )

    async def prompt_delete(self, prompt_id: int, telegram_id: int) -> None:
        await self.pool.execute(
            "DELETE FROM saved_prompts WHERE id=$1 AND telegram_id=$2", prompt_id, telegram_id
        )

    # --- Payments --------------------------------------------------------
    async def payment_insert(
        self, telegram_id: int, provider: str, amount: Any, currency: str, charge_id: str | None
    ) -> None:
        await self.pool.execute(
            "INSERT INTO payments (telegram_id, provider, amount, currency, charge_id) "
            "VALUES ($1, $2, $3, $4, $5)",
            telegram_id, provider, amount, currency, charge_id,
        )

    async def payments_today(self, telegram_id: int) -> int:
        """Pro grants recorded for this user since UTC midnight (velocity guard)."""
        return await self.pool.fetchval(
            "SELECT count(*) FROM payments WHERE telegram_id=$1 "
            "AND created_at >= date_trunc('day', now())",
            telegram_id,
        )

    # --- Deletion (privacy) ----------------------------------------------
    async def delete_user(self, telegram_id: int) -> None:
        """Delete all rows tied to a telegram_id (media_cache is anonymous)."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM payments WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM saved_prompts WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM usage_daily WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM users WHERE telegram_id=$1", telegram_id)
