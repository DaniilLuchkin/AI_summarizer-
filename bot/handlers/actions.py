"""Inline-keyboard callbacks: stage an action, then run it with optional context.

Tapping a predefined action no longer runs it immediately. Instead it posts the
action label as a bold "command" and waits (FSM `awaiting_input`) for the user
to optionally add context (text / file / link) before running — or to tap
"▶️ Run" to run with none. The custom button enters the same state but treats
the user's next text as the instruction itself.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers import collect, execute
from bot.handlers.run import ACTION_CB_PREFIX, RUN_CB, ActionStates, build_run_keyboard
from bot.prompts import CUSTOM_KEY, label_key
from bot.runtime import AppContext
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)


def build_router(ctx: AppContext) -> Router:
    router = Router(name="actions")

    def _lang(message: Message, fallback_code: str | None) -> str:
        chat_state = ctx.store.get(message.chat.id)
        return chat_state.lang if chat_state else resolve_lang(fallback_code)

    # --- Stage an action ------------------------------------------------
    @router.callback_query(F.data.startswith(ACTION_CB_PREFIX))
    async def on_action(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()  # clear the loading spinner
        key = callback.data[len(ACTION_CB_PREFIX):]
        message = callback.message
        if message is None:
            return
        lang = _lang(message, callback.from_user.language_code)

        chat_state = ctx.store.get(message.chat.id)
        if chat_state is None or not chat_state.has_active_batch:
            await message.answer(t("no_active_batch", lang))
            return

        await state.set_state(ActionStates.awaiting_input)
        await state.update_data(action_key=key)

        if key == CUSTOM_KEY:
            # Custom: ask for the prompt; the next text becomes the instruction.
            await message.answer(t("custom_prompt_ask", lang))
            return

        # Predefined: the bold command IS the echo; then offer context / Run.
        label = t(label_key(key), lang)
        await message.answer(f"<b>{label}</b>", parse_mode="HTML")
        await message.answer(t("action_context_hint", lang), reply_markup=build_run_keyboard(lang))

    # --- Run staged action with no added context ------------------------
    @router.callback_query(ActionStates.awaiting_input, F.data == RUN_CB)
    async def on_run(callback: CallbackQuery, state: FSMContext, bot) -> None:
        await callback.answer()
        message = callback.message
        if message is None:
            return
        data = await state.get_data()
        key = data.get("action_key")
        lang = _lang(message, callback.from_user.language_code)
        await state.clear()
        await execute.run_staged(
            ctx, message, bot, lang, callback.from_user.id, key, source_message=None
        )

    # --- The user's context message (or a new-batch trigger) ------------
    @router.message(ActionStates.awaiting_input)
    async def on_staged_message(message: Message, state: FSMContext, bot) -> None:
        lang = _lang(message, message.from_user.language_code)
        data = await state.get_data()
        key = data.get("action_key")

        # Forwarded / media -> start a NEW batch instead of treating as context.
        if collect.is_new_batch_trigger(message):
            await state.clear()
            await collect.handle_incoming(ctx, message, state, bot)
            return

        await state.clear()
        await execute.run_staged(
            ctx, message, bot, lang, message.from_user.id, key, source_message=message
        )

    return router
