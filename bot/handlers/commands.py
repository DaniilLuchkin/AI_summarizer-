"""/start and /reset command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import texts
from bot.runtime import AppContext


def build_router(ctx: AppContext) -> Router:
    router = Router(name="commands")

    @router.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(texts.START)

    @router.message(Command("reset"))
    async def reset(message: Message, state: FSMContext) -> None:
        # Clear in-memory batch (and cancel any pending debounce timer) + FSM.
        ctx.store.reset(message.chat.id)
        await state.clear()
        await message.answer(texts.RESET_DONE)

    return router
