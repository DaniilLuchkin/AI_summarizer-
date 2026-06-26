"""Per-task model selection for BYO-key users.

Fetches OpenRouter's live model catalog (cached ~1h), filters it per slot
(text / vision / transcribe / image), validates custom slugs, and resolves the
effective model for a user — their override only applies while a key is set.
"""

from __future__ import annotations

import logging
import time

from bot.config import Settings
from bot.services.db import Database
from bot.services.openrouter import OpenRouterClient
from bot.services.quota import Quota

logger = logging.getLogger(__name__)

SLOTS = ("text", "vision", "transcribe", "image")
_CATALOG_TTL = 3600  # seconds
_SHORTLIST_SIZE = 6

# Used when the catalog has no clean speech-to-text flag.
_TRANSCRIBE_FALLBACK = [
    "openai/whisper-large-v3",
    "openai/whisper-large-v3-turbo",
    "openai/gpt-4o-transcribe",
]


def _input_mods(entry: dict) -> list[str]:
    return (entry.get("architecture") or {}).get("input_modalities") or []


def _output_mods(entry: dict) -> list[str]:
    return (entry.get("architecture") or {}).get("output_modalities") or []


def _matches_slot(entry: dict, slot: str) -> bool:
    """Best-effort modality filter for a catalog entry."""
    ins, outs = _input_mods(entry), _output_mods(entry)
    if slot == "text":
        return "text" in ins and "text" in outs and "image" not in outs
    if slot == "vision":
        return "image" in ins
    if slot == "image":
        return "image" in outs
    if slot == "transcribe":
        return "audio" in ins
    return False


def _price_per_mtok(entry: dict) -> str:
    """Human-readable prompt price per 1M tokens, or '—'."""
    try:
        prompt = float((entry.get("pricing") or {}).get("prompt", 0))
    except (TypeError, ValueError):
        return "—"
    if prompt <= 0:
        return "free" if prompt == 0 else "—"
    return f"${prompt * 1_000_000:.2f}/M"


def _summarize(entry: dict) -> dict:
    return {
        "id": entry.get("id", ""),
        "name": entry.get("name") or entry.get("id", ""),
        "context": entry.get("context_length"),
        "price": _price_per_mtok(entry),
    }


class ModelService:
    def __init__(self, db: Database, settings: Settings, orclient: OpenRouterClient, quota: Quota):
        self.db = db
        self.s = settings
        self.orclient = orclient
        self.quota = quota
        self._cache: tuple[float, list[dict]] | None = None  # (fetched_at, catalog)

    # --- Catalog ---------------------------------------------------------
    async def get_catalog(self, api_key: str | None) -> list[dict]:
        """OpenRouter catalog, cached in memory with a TTL."""
        now = time.time()
        if self._cache is not None and now - self._cache[0] < _CATALOG_TTL:
            return self._cache[1]
        try:
            catalog = await self.orclient.list_models(api_key)
        except Exception:  # noqa: BLE001 - serve stale cache if a refetch fails
            logger.warning("Model catalog fetch failed")
            return self._cache[1] if self._cache else []
        self._cache = (now, catalog)
        return catalog

    async def shortlist_for(self, slot: str, api_key: str | None) -> list[dict]:
        """Top filtered models for a slot (name + context + price)."""
        catalog = await self.get_catalog(api_key)
        filtered = [m for m in catalog if _matches_slot(m, slot)]
        if slot == "transcribe" and not filtered:
            # Catalog didn't flag STT — fall back to a known shortlist.
            by_id = {m.get("id"): m for m in catalog}
            filtered = [by_id.get(s, {"id": s, "name": s}) for s in _TRANSCRIBE_FALLBACK]
        return [_summarize(m) for m in filtered[:_SHORTLIST_SIZE]]

    async def slug_exists(self, slug: str, api_key: str | None) -> bool:
        catalog = await self.get_catalog(api_key)
        return any(m.get("id") == slug for m in catalog)

    async def modality_ok(self, slug: str, slot: str, api_key: str | None) -> bool:
        catalog = await self.get_catalog(api_key)
        entry = next((m for m in catalog if m.get("id") == slug), None)
        return entry is not None and _matches_slot(entry, slot)

    # --- Per-user prefs --------------------------------------------------
    async def get_user_models(self, telegram_id: int) -> dict[str, str | None]:
        row = await self.db.get_user_models(telegram_id)
        if row is None:
            return {slot: None for slot in SLOTS}
        return {
            "text": row["model_text"],
            "vision": row["model_vision"],
            "transcribe": row["model_transcribe"],
            "image": row["model_image"],
        }

    async def set_user_model(self, telegram_id: int, slot: str, slug: str) -> None:
        await self.db.set_user_model(telegram_id, slot, slug)

    async def reset_user_model(self, telegram_id: int, slot: str) -> None:
        await self.db.set_user_model(telegram_id, slot, None)

    async def reset_all(self, telegram_id: int) -> None:
        await self.db.reset_user_models(telegram_id)

    # --- Resolution ------------------------------------------------------
    def _default(self, slot: str) -> str:
        return {
            "vision": self.s.model_vision,
            "transcribe": self.s.model_transcribe,
            "image": self.s.model_image,
        }.get(slot, self.s.model_text)

    async def resolve(self, telegram_id: int, slot: str) -> str:
        """Effective model: BYO override (only while a key is set) else default.

        The text-slot default preserves existing behaviour (Pro/BYO users get the
        Pro text model via quota.model_for); other slots use the global default.
        """
        user = await self.db.get_user(telegram_id)
        if user is not None and self.quota.has_byo(user):
            prefs = await self.get_user_models(telegram_id)
            if prefs.get(slot):
                return prefs[slot]
        if slot == "text":
            return await self.quota.model_for(telegram_id)
        return self._default(slot)
