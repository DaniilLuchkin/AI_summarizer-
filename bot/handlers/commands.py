"""/start and /reset command handlers (language-aware)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.runtime import AppContext
from bot.texts import resolve_lang, t


def build_router(ctx: AppContext) -> Router:
    router = Router(name="commands")

    @router.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        lang = resolve_lang(message.from_user.language_code)
        # Remember the language for this chat's session.
        ctx.store.get_or_create(message.chat.id).lang = lang
        await state.clear()
        await message.answer(t("welcome", lang))

    @router.message(Command("reset"))
    async def reset(message: Message, state: FSMContext) -> None:
        lang = resolve_lang(message.from_user.language_code)
        ctx.store.reset(message.chat.id)
        await state.clear()
        await message.answer(t("reset_done", lang))

    return router
