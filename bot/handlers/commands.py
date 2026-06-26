"""/start, /reset, /help, /lang.

Commands respond in ANY FSM state (no state filter) and abort any in-progress
action / custom-prompt flow by clearing the FSM. Language lives in the in-memory
session (see BatchStore); a manual /lang choice is an override that sticks across
/start, /reset and new batches, and beats Telegram's language_code.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.commands_menu import COMMANDS
from bot.runtime import AppContext
from bot.texts import resolve_lang, t

LANG_CB_PREFIX = "lang:"


def build_router(ctx: AppContext) -> Router:
    router = Router(name="commands")

    def _lang(message: Message) -> str:
        # Override > detected > language_code > en.
        return ctx.store.get_lang(message.chat.id) or resolve_lang(
            message.from_user.language_code
        )

    @router.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext) -> None:
        # Keep any manual override; otherwise lock in the detected language.
        lang = _lang(message)
        ctx.store.set_lang(message.chat.id, lang)
        await state.clear()
        ctx.store.clear_session(message.chat.id)
        await message.answer(t("welcome", lang))

    @router.message(Command("reset"))
    async def cmd_reset(message: Message, state: FSMContext) -> None:
        lang = _lang(message)
        await state.clear()
        ctx.store.clear_session(message.chat.id)  # keeps language
        await message.answer(t("reset_done", lang))

    @router.message(Command("help"))
    async def cmd_help(message: Message, state: FSMContext) -> None:
        # Aborts any in-progress FSM but does NOT touch the batch buffer.
        await state.clear()
        await message.answer(t("help", _lang(message)))

    @router.message(Command("lang"))
    async def cmd_lang(message: Message, state: FSMContext) -> None:
        await state.clear()
        lang = _lang(message)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🇬🇧 English", callback_data=f"{LANG_CB_PREFIX}en"),
                    InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"{LANG_CB_PREFIX}ru"),
                    InlineKeyboardButton(text="🇺🇦 Українська", callback_data=f"{LANG_CB_PREFIX}uk"),
                ]
            ]
        )
        await message.answer(t("lang_choose", lang), reply_markup=keyboard)

    @router.callback_query(F.data.startswith(LANG_CB_PREFIX))
    async def set_lang_cb(callback: CallbackQuery) -> None:
        chosen = callback.data[len(LANG_CB_PREFIX):]
        if chosen not in ("en", "ru", "uk"):
            chosen = "en"
        ctx.store.set_lang_override(callback.message.chat.id, chosen)
        await callback.answer()
        # Relabel this chat's command menu to the chosen language.
        await callback.bot.set_my_commands(
            COMMANDS[chosen], scope=BotCommandScopeChat(chat_id=callback.message.chat.id)
        )
        await callback.message.edit_text(t("lang_set", chosen))

    return router
