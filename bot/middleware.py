"""Outer middleware that enforces the ALLOWED_USER_IDS allow-list.

Empty allow-list == public bot. When a list is set, anyone else is politely
turned away and their update is dropped before reaching any handler.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.config import Settings
from bot.texts import resolve_lang, t


class AccessMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and not self._settings.is_user_allowed(user.id):
            await self._deny(event, resolve_lang(user.language_code))
            return None  # drop the update
        return await handler(event, data)

    @staticmethod
    async def _deny(event: Update, lang: str) -> None:
        """Tell the user they're not allowed, in their language."""
        if isinstance(event.event, Message):
            await event.event.answer(t("not_allowed", lang))
        elif isinstance(event.event, CallbackQuery):
            await event.event.answer(t("not_allowed", lang), show_alert=True)
