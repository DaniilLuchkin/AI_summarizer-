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
        referred_by: int | None,
    ) -> asyncpg.Record | None:
        """Insert a user if absent. Returns the row, or None if it already existed.

        Credit balances start at 0; the signup bonus is granted explicitly (once)
        by the credit service so it is logged in the ledger.
        """
        return await self.pool.fetchrow(
            """
            INSERT INTO users (telegram_id, referral_code, referred_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
            RETURNING *
            """,
            telegram_id, referral_code, referred_by,
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

    # --- Credits (all amounts in INTEGER tenths of a credit) -------------
    async def refresh_daily(self, telegram_id: int, floor_tenths: int, today: dt.date) -> None:
        """Reset the daily free bucket to `floor_tenths` once per day (set, not add)."""
        await self.pool.execute(
            "UPDATE users SET daily_credits=$2, daily_credits_date=$3 "
            "WHERE telegram_id=$1 AND daily_credits_date IS DISTINCT FROM $3",
            telegram_id, floor_tenths, today,
        )

    async def grant_credits(self, telegram_id: int, tenths: int, reason: str) -> None:
        """Add `tenths` to the persistent bucket and log it."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE users SET credits = credits + $2 WHERE telegram_id=$1",
                    telegram_id, tenths,
                )
                await conn.execute(
                    "INSERT INTO credit_ledger (telegram_id, delta, bucket, reason) "
                    "VALUES ($1, $2, 'persistent', $3)",
                    telegram_id, tenths, reason,
                )

    async def charge_credits(
        self, telegram_id: int, tenths: int, reason: str
    ) -> tuple[int, int] | None:
        """Atomically spend `tenths`: daily bucket first, then persistent.

        Returns (from_daily, from_persistent) on success, or None if the combined
        balance is insufficient (nothing is charged). Logs one ledger row/bucket.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT credits, daily_credits FROM users WHERE telegram_id=$1 FOR UPDATE",
                    telegram_id,
                )
                if row is None:
                    return None
                daily, persistent = row["daily_credits"], row["credits"]
                if daily + persistent < tenths:
                    return None
                from_daily = min(daily, tenths)
                from_persistent = tenths - from_daily
                await conn.execute(
                    "UPDATE users SET daily_credits = daily_credits - $2, "
                    "credits = credits - $3 WHERE telegram_id=$1",
                    telegram_id, from_daily, from_persistent,
                )
                if from_daily:
                    await conn.execute(
                        "INSERT INTO credit_ledger (telegram_id, delta, bucket, reason) "
                        "VALUES ($1, $2, 'daily', $3)",
                        telegram_id, -from_daily, reason,
                    )
                if from_persistent:
                    await conn.execute(
                        "INSERT INTO credit_ledger (telegram_id, delta, bucket, reason) "
                        "VALUES ($1, $2, 'persistent', $3)",
                        telegram_id, -from_persistent, reason,
                    )
                return from_daily, from_persistent

    async def mark_signup_granted(self, telegram_id: int) -> bool:
        """Flip signup_bonus_granted to TRUE once. Returns True if it was flipped."""
        val = await self.pool.fetchval(
            "UPDATE users SET signup_bonus_granted=TRUE "
            "WHERE telegram_id=$1 AND signup_bonus_granted=FALSE RETURNING TRUE",
            telegram_id,
        )
        return bool(val)

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

    # --- Per-task model overrides ----------------------------------------
    # Maps a slot name to its column. Used to build safe SQL (whitelisted names).
    _MODEL_COLUMNS = {
        "text": "model_text",
        "vision": "model_vision",
        "transcribe": "model_transcribe",
        "image": "model_image",
    }

    async def get_user_models(self, telegram_id: int) -> asyncpg.Record | None:
        return await self.pool.fetchrow(
            "SELECT * FROM user_models WHERE telegram_id=$1", telegram_id
        )

    async def set_user_model(self, telegram_id: int, slot: str, slug: str | None) -> None:
        """Upsert one slot's override (slug=None clears it -> global default)."""
        column = self._MODEL_COLUMNS[slot]  # KeyError on bad slot is intentional
        await self.pool.execute(
            f"""
            INSERT INTO user_models (telegram_id, {column}) VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO UPDATE SET {column}=EXCLUDED.{column}, updated_at=now()
            """,
            telegram_id, slug,
        )

    async def reset_user_models(self, telegram_id: int) -> None:
        await self.pool.execute("DELETE FROM user_models WHERE telegram_id=$1", telegram_id)

    # --- Deletion (privacy) ----------------------------------------------
    async def delete_user(self, telegram_id: int) -> None:
        """Delete all rows tied to a telegram_id (media_cache is anonymous)."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM payments WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM saved_prompts WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM usage_daily WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM user_models WHERE telegram_id=$1", telegram_id)
                await conn.execute("DELETE FROM users WHERE telegram_id=$1", telegram_id)
