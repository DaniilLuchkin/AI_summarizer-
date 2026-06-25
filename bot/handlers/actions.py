"""Inline-keyboard callbacks: run a predefined action or open the custom prompt."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot import texts
from bot.handlers.run import ACTION_CB_PREFIX, CustomStates, run_llm
from bot.prompts import ACTIONS_BY_KEY, CUSTOM_KEY
from bot.runtime import AppContext

logger = logging.getLogger(__name__)


def build_router(ctx: AppContext) -> Router:
    router = Router(name="actions")

    @router.callback_query(F.data.startswith(ACTION_CB_PREFIX))
    async def on_action(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()  # stop Telegram's loading spinner
        key = callback.data[len(ACTION_CB_PREFIX):]
        message = callback.message
        if message is None:
            return

        chat_state = ctx.store.get(message.chat.id)
        if chat_state is None or not chat_state.has_active_batch:
            await message.answer(texts.NO_ACTIVE_BATCH)
            return

        # The custom-prompt button switches the chat into the FSM input state.
        if key == CUSTOM_KEY:
            await state.set_state(CustomStates.waiting_for_instruction)
            await message.answer(texts.CUSTOM_PROMPT_ASK)
            return

        action = ACTIONS_BY_KEY.get(key)
        if action is None:
            await message.answer(texts.GENERIC_ERROR)
            return

        document, truncated = ctx.store.assemble_for_llm(chat_state)
        if truncated:
            await message.answer(texts.CONTEXT_TRUNCATED)

        await run_llm(
            message,
            ctx,
            user_id=callback.from_user.id,
            system_prompt=action.system_prompt,
            user_content=document,
        )

    return router
