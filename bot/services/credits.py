"""Credit ledger: a single understandable balance, charged by real usage.

Two buckets, both stored as INTEGER **tenths** of a credit (1 credit = 10) to
avoid float drift:

* **persistent** — signup bonus + referrals + purchases + Pro monthly grants.
  Never auto-resets, no expiry.
* **daily** — a free floor that is *reset* (not added) to ``DAILY_FREE_CREDITS``
  each day for non-Pro users; use-it-or-lose-it. Spent **before** persistent.

Pricing (env values are in credits; converted to tenths here):
* text  — by input+output tokens: ``round(tokens / TEXT_TOKENS_PER_CREDIT * 10)``,
  minimum 1 tenth, charged AFTER a successful response.
* audio — ``round(seconds / 60 * CREDITS_AUDIO_PER_MIN * 10)`` (no whole-credit
  rounding: 90 s → 1.5, 30 s → 0.5).
* photo — ``CREDITS_PHOTO`` per analyzed photo.

BYO-key users bypass the whole system (callers skip charging). Every user-facing
number is rendered with exactly one decimal via :func:`fmt`.
"""

from __future__ import annotations

import datetime as dt
import logging

from bot.config import Settings
from bot.services.db import Database

logger = logging.getLogger(__name__)


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def fmt(tenths: int) -> str:
    """Render tenths as a one-decimal credit string ('35' -> '3.5')."""
    return f"{tenths / 10:.1f}"


def _to_tenths(credits: float) -> int:
    return round(credits * 10)


class CreditService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.s = settings

    # --- Pricing (tenths) ------------------------------------------------
    def text_cost_tenths(self, total_tokens: int) -> int:
        per = max(self.s.text_tokens_per_credit, 1)
        return max(1, round(total_tokens / per * 10))

    def audio_cost_tenths(self, seconds: float) -> int:
        return round(max(seconds, 0) / 60 * self.s.credits_audio_per_min * 10)

    def photo_cost_tenths(self) -> int:
        return _to_tenths(self.s.credits_photo)

    # --- Pro / floor helpers --------------------------------------------
    @staticmethod
    def _is_pro(user) -> bool:
        until = user["pro_until"] if user else None
        return until is not None and until > dt.datetime.now(dt.timezone.utc)

    def daily_floor_tenths(self, user) -> int:
        if self._is_pro(user):
            return 0  # Pro users live off the persistent bucket
        return _to_tenths(self.s.daily_free_credits)

    # --- Bucket operations ----------------------------------------------
    async def refresh_daily(self, telegram_id: int) -> None:
        user = await self.db.get_user(telegram_id)
        if user is None:
            return
        await self.db.refresh_daily(telegram_id, self.daily_floor_tenths(user), _today())

    async def balance(self, telegram_id: int) -> tuple[int, int]:
        """Return (persistent_tenths, daily_tenths) after a daily refresh."""
        await self.refresh_daily(telegram_id)
        user = await self.db.get_user(telegram_id)
        if user is None:
            return 0, 0
        return user["credits"], user["daily_credits"]

    async def has_any(self, telegram_id: int) -> bool:
        persistent, daily = await self.balance(telegram_id)
        return (persistent + daily) > 0

    async def grant(self, telegram_id: int, tenths: int, reason: str) -> None:
        if tenths <= 0:
            return
        await self.db.grant_credits(telegram_id, tenths, reason)

    async def charge(self, telegram_id: int, tenths: int, reason: str) -> tuple[bool, str | None]:
        """Spend `tenths` (daily first, then persistent). (ok, reason_code)."""
        if tenths <= 0:
            return True, None
        await self.refresh_daily(telegram_id)
        result = await self.db.charge_credits(telegram_id, tenths, reason)
        if result is None:
            return False, "credits"
        return True, None

    # --- Named grants ----------------------------------------------------
    async def grant_signup_bonus(self, telegram_id: int) -> None:
        """Grant the one-time signup bonus (idempotent via signup_bonus_granted)."""
        if await self.db.mark_signup_granted(telegram_id):
            await self.grant(telegram_id, _to_tenths(self.s.signup_bonus_credits), "signup_bonus")

    async def grant_referral(self, telegram_id: int) -> None:
        await self.grant(telegram_id, _to_tenths(self.s.referral_bonus_credits), "referral")

    async def grant_pro_monthly(self, telegram_id: int) -> None:
        await self.grant(telegram_id, _to_tenths(self.s.pro_monthly_credits), "pro_grant")

    async def grant_pack(self, telegram_id: int, credits: int) -> None:
        await self.grant(telegram_id, credits * 10, "buy_pack")
