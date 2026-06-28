"""Pro/BYO gating, user lifecycle, and BYO-key encryption.

Usage is metered by the credit ledger (services/credits.py); this module owns
the durable user row: Pro status, the bring-your-own-key, the per-task text
model, the context window, and first-touch grants (signup bonus + referral),
all logged to the credit ledger.
"""

from __future__ import annotations

import datetime as dt
import logging
import secrets

from cryptography.fernet import Fernet, InvalidToken

from bot.config import Settings
from bot.services.db import Database

logger = logging.getLogger(__name__)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _to_tenths(credits: float) -> int:
    return round(credits * 10)


class Quota:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.s = settings
        # Fernet is optional: without APP_SECRET, BYO-key features are disabled.
        self._fernet = Fernet(settings.app_secret.encode()) if settings.app_secret else None

    # --- User lifecycle --------------------------------------------------
    async def ensure_user(self, telegram_id: int, referred_by: int | None = None):
        """Return the user row, creating it once, and grant first-touch credits."""
        user = await self.db.get_user(telegram_id)
        if user is not None:
            await self._ensure_signup_bonus(telegram_id)
            return user

        if referred_by == telegram_id:
            referred_by = None  # can't refer yourself

        created = await self.db.create_user(
            telegram_id, self._gen_referral_code(telegram_id), referred_by
        )
        if created is None:
            # Lost a creation race; just return the existing row.
            return await self.db.get_user(telegram_id)

        await self._ensure_signup_bonus(telegram_id)
        # Referral grant: both parties, once, at first signup.
        if referred_by is not None:
            ref = _to_tenths(self.s.referral_bonus_credits)
            await self.db.grant_credits(referred_by, ref, "referral")
            await self.db.grant_credits(telegram_id, ref, "referral")
        return await self.db.get_user(telegram_id)

    async def _ensure_signup_bonus(self, telegram_id: int) -> None:
        """Grant the one-time signup bonus (also back-fills migrated users)."""
        if await self.db.mark_signup_granted(telegram_id):
            await self.db.grant_credits(
                telegram_id, _to_tenths(self.s.signup_bonus_credits), "signup_bonus"
            )

    @staticmethod
    def _gen_referral_code(telegram_id: int) -> str:
        return f"{telegram_id:x}{secrets.token_hex(2)}"

    # --- Status helpers --------------------------------------------------
    def is_pro(self, user) -> bool:
        pro_until = user["pro_until"]
        return pro_until is not None and pro_until > _utc_now()

    def has_byo(self, user) -> bool:
        return bool(user["byo_key_enc"]) and self._fernet is not None

    @property
    def fernet_available(self) -> bool:
        return self._fernet is not None

    # --- BYO key crypto --------------------------------------------------
    def encrypt_key(self, raw_key: str) -> str:
        if self._fernet is None:
            raise RuntimeError("APP_SECRET not configured")
        return self._fernet.encrypt(raw_key.encode()).decode()

    def decrypt_key(self, enc: str) -> str | None:
        if self._fernet is None:
            return None
        try:
            return self._fernet.decrypt(enc.encode()).decode()
        except (InvalidToken, ValueError):
            logger.warning("Failed to decrypt a stored BYO key")
            return None

    async def api_key_for(self, telegram_id: int) -> str | None:
        """Decrypted BYO key for the user, or None to use the global key."""
        user = await self.ensure_user(telegram_id)
        if not self.has_byo(user):
            return None
        return self.decrypt_key(user["byo_key_enc"])

    async def has_byo_key(self, telegram_id: int) -> bool:
        user = await self.ensure_user(telegram_id)
        return self.has_byo(user)

    async def model_for(self, telegram_id: int) -> str:
        """Pro/BYO users get the Pro text model; everyone else the standard one."""
        user = await self.ensure_user(telegram_id)
        if self.is_pro(user) or self.has_byo(user):
            return self.s.text_model_pro
        return self.s.model_text

    async def context_cap_for(self, telegram_id: int) -> int:
        user = await self.ensure_user(telegram_id)
        if self.is_pro(user) or self.has_byo(user):
            return self.s.max_context_chars_pro
        return self.s.max_context_chars
