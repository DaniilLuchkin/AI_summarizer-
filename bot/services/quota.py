"""Limits, quotas, Pro/BYO gating, and BYO-key encryption.

Free tier: a one-time signup bonus pool (consumed before the daily allowance)
plus daily audio/photo/LLM allowances. Image (🎨) and Presentation (📊) are
Pro-only. Pro: generous daily caps that bound cost. BYO-key: bypasses all quotas.

Reason codes returned by consume/require map to texts keys at the call site:
  "audio" -> limit_audio, "photo" -> limit_photo, "llm" -> limit_llm,
  "image" -> paywall_image, "pptx" -> paywall_pptx, "generic" -> paywall_generic.
"""

from __future__ import annotations

import datetime as dt
import logging
import secrets

from cryptography.fernet import Fernet, InvalidToken

from bot.config import Settings
from bot.services.db import Database

logger = logging.getLogger(__name__)


def _utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Quota:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.s = settings
        # Fernet is optional: without APP_SECRET, BYO-key features are disabled.
        self._fernet = Fernet(settings.app_secret.encode()) if settings.app_secret else None

    # --- User lifecycle --------------------------------------------------
    async def ensure_user(self, telegram_id: int, referred_by: int | None = None):
        """Return the user row, creating it (with signup bonus + referral) once."""
        user = await self.db.get_user(telegram_id)
        if user is not None:
            return user

        if referred_by == telegram_id:
            referred_by = None  # can't refer yourself

        created = await self.db.create_user(
            telegram_id,
            self._gen_referral_code(telegram_id),
            self.s.free_signup_audio_sec,
            self.s.free_signup_photos,
            referred_by,
        )
        if created is None:
            # Lost a creation race; just return the existing row.
            return await self.db.get_user(telegram_id)

        # Referral grant applies only at first signup, once per new user.
        if referred_by is not None:
            await self.db.add_bonus(
                referred_by, self.s.referral_bonus_audio_sec, self.s.referral_bonus_photos
            )
            await self.db.add_bonus(
                telegram_id, self.s.referral_bonus_audio_sec, self.s.referral_bonus_photos
            )
            return await self.db.get_user(telegram_id)
        return created

    @staticmethod
    def _gen_referral_code(telegram_id: int) -> str:
        # Short, unlikely-to-collide code; UNIQUE constraint is the real guard.
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

    def _daily_caps(self, user) -> dict[str, int]:
        if self.is_pro(user):
            return {
                "audio": self.s.pro_daily_audio_sec,
                "photos": self.s.pro_daily_photos,
                "llm": self.s.pro_daily_llm_calls,
                "images": self.s.pro_daily_images,
                "pptx": self.s.pro_daily_pptx,
            }
        return {
            "audio": self.s.free_daily_audio_sec,
            "photos": self.s.free_daily_photos,
            "llm": self.s.free_daily_llm_calls,
            "images": 0,  # Pro-only
            "pptx": 0,    # Pro-only
        }

    async def remaining(self, telegram_id: int) -> dict:
        user = await self.ensure_user(telegram_id)
        usage = await self.db.get_usage(telegram_id, _utc_today())
        used = {
            k: (usage[k] if usage else 0)
            for k in ("audio_sec", "photos", "llm_calls", "images", "pptx")
        }
        caps = self._daily_caps(user)
        return {
            "pro": self.is_pro(user),
            "byo": self.has_byo(user),
            "pro_until": user["pro_until"],
            "referral_code": user["referral_code"],
            "bonus_audio_sec": user["bonus_audio_sec"],
            "bonus_photos": user["bonus_photos"],
            "audio_sec": max(caps["audio"] - used["audio_sec"], 0) + user["bonus_audio_sec"],
            "photos": max(caps["photos"] - used["photos"], 0) + user["bonus_photos"],
            "llm_calls": max(caps["llm"] - used["llm_calls"], 0),
            "images": max(caps["images"] - used["images"], 0),
            "pptx": max(caps["pptx"] - used["pptx"], 0),
        }

    # --- Consumption -----------------------------------------------------
    async def consume_audio(self, telegram_id: int, seconds: int) -> tuple[bool, str | None]:
        user = await self.ensure_user(telegram_id)
        if self.has_byo(user):
            return True, None
        seconds = max(int(seconds), 0)
        if seconds == 0:
            return True, None

        take_bonus = min(seconds, user["bonus_audio_sec"])
        rest = seconds - take_bonus
        cap = self._daily_caps(user)["audio"]
        usage = await self.db.get_usage(telegram_id, _utc_today())
        used = usage["audio_sec"] if usage else 0
        if rest > 0 and used + rest > cap:
            return False, "audio"

        if take_bonus > 0:
            await self.db.consume_bonus(telegram_id, take_bonus, 0)
        if rest > 0:
            await self.db.incr_usage(telegram_id, _utc_today(), audio_sec=rest)
        return True, None

    async def consume_photo(self, telegram_id: int, n: int = 1) -> tuple[bool, str | None]:
        user = await self.ensure_user(telegram_id)
        if self.has_byo(user):
            return True, None

        take_bonus = min(n, user["bonus_photos"])
        rest = n - take_bonus
        cap = self._daily_caps(user)["photos"]
        usage = await self.db.get_usage(telegram_id, _utc_today())
        used = usage["photos"] if usage else 0
        if rest > 0 and used + rest > cap:
            return False, "photo"

        if take_bonus > 0:
            await self.db.consume_bonus(telegram_id, 0, take_bonus)
        if rest > 0:
            await self.db.incr_usage(telegram_id, _utc_today(), photos=rest)
        return True, None

    async def consume_llm_call(self, telegram_id: int) -> tuple[bool, str | None]:
        user = await self.ensure_user(telegram_id)
        if self.has_byo(user):
            return True, None
        cap = self._daily_caps(user)["llm"]
        usage = await self.db.get_usage(telegram_id, _utc_today())
        used = usage["llm_calls"] if usage else 0
        if used + 1 > cap:
            return False, "llm"
        await self.db.incr_usage(telegram_id, _utc_today(), llm_calls=1)
        return True, None

    async def require_image(self, telegram_id: int) -> tuple[bool, str | None]:
        user = await self.ensure_user(telegram_id)
        if self.has_byo(user):
            return True, None
        if not self.is_pro(user):
            return False, "image"  # Pro-only feature -> paywall
        cap = self._daily_caps(user)["images"]
        usage = await self.db.get_usage(telegram_id, _utc_today())
        used = usage["images"] if usage else 0
        if used + 1 > cap:
            return False, "generic"
        await self.db.incr_usage(telegram_id, _utc_today(), images=1)
        return True, None

    async def require_pptx(self, telegram_id: int) -> tuple[bool, str | None]:
        user = await self.ensure_user(telegram_id)
        if self.has_byo(user):
            return True, None
        if not self.is_pro(user):
            return False, "pptx"  # Pro-only feature -> paywall
        cap = self._daily_caps(user)["pptx"]
        usage = await self.db.get_usage(telegram_id, _utc_today())
        used = usage["pptx"] if usage else 0
        if used + 1 > cap:
            return False, "generic"
        await self.db.incr_usage(telegram_id, _utc_today(), pptx=1)
        return True, None

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
