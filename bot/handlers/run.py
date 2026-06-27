"""Shared helpers: FSM states, keyboards, and the rate-limited LLM text call."""

from __future__ import annotations

import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.prompts import (
    CUSTOM_KEY,
    MORE_ACTION_KEYS,
    PRIMARY_ACTION_KEYS,
    PRO_ACTION_KEYS,
    label_key,
)
from bot.runtime import AppContext
from bot.services.delivery import deliver_answer
from bot.services.openrouter import OpenRouterError
from bot.texts import t

logger = logging.getLogger(__name__)

# Callback data prefixes / constants.
ACTION_CB_PREFIX = "act:"   # act:<key> — stage a predefined action or custom
RUN_CB = "run:now"          # run the staged action without added context
UPGRADE_CB = "upgrade"      # open the Pro purchase options (handled in billing)
MORE_CB = "more:open"       # open the "More…" actions submenu (in-place)
BACK_CB = "more:back"       # return from the submenu to the primary grid


def build_upgrade_keyboard(lang: str) -> InlineKeyboardMarkup:
    """One-tap "⭐ Upgrade to Pro" button, attached to every paywall/limit reply."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn_upgrade", lang), callback_data=UPGRADE_CB)]]
    )


class ActionStates(StatesGroup):
    """A predefined action (or custom) is staged, awaiting optional context."""

    awaiting_input = State()  # FSM data holds {"action_key": <key>}


def _grid(keys: list[str], lang: str, locked: set[str] | None = None) -> list[list[InlineKeyboardButton]]:
    """Lay action keys out 2-per-row, flagging `locked` keys with a 🔒."""
    locked = locked or set()
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in keys:
        label = t(label_key(key), lang)
        if key in locked:
            label = f"{label} 🔒"
        row.append(InlineKeyboardButton(text=label, callback_data=f"{ACTION_CB_PREFIX}{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def build_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Primary grid: the most-used actions, then Custom, then a 'More…' submenu."""
    rows = _grid(PRIMARY_ACTION_KEYS, lang)
    rows.append(
        [InlineKeyboardButton(
            text=t(label_key(CUSTOM_KEY), lang), callback_data=f"{ACTION_CB_PREFIX}{CUSTOM_KEY}"
        )]
    )
    rows.append([InlineKeyboardButton(text=t("btn_more", lang), callback_data=MORE_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_more_keyboard(lang: str, entitled: bool = True) -> InlineKeyboardMarkup:
    """The 'More…' submenu: secondary + export actions (Pro ones 🔒 if not entitled)."""
    locked = set() if entitled else PRO_ACTION_KEYS
    rows = _grid(MORE_ACTION_KEYS, lang, locked)
    rows.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data=BACK_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_run_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Single "▶️ Run" button shown under a staged action."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn_run", lang), callback_data=RUN_CB)]]
    )


async def run_llm(
    message: Message,
    ctx: AppContext,
    lang: str,
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    api_key: str | None = None,
    show_keyboard: bool = True,
    formatted: bool = False,
    as_file: bool = False,
) -> None:
    """Call the text model and deliver the (streamed) result as plain text.

    Quota gating happens in execute.run_staged before calling this. `model` /
    `api_key` support the Pro model and bring-your-own-key. `formatted` / `as_file`
    are set only when the user explicitly asked for formatting / a file.
    """
    try:
        await deliver_answer(
            message,
            ctx,
            lang,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=model,
            api_key=api_key,
            formatted=formatted,
            as_file=as_file,
        )
        if show_keyboard:
            await message.answer(t("followup_hint", lang), reply_markup=build_actions_keyboard(lang))
    except OpenRouterError:
        logger.exception("LLM call failed")
        await message.answer(t("llm_error", lang))
    except Exception:  # noqa: BLE001 - never crash the polling loop
        logger.exception("Unexpected error during LLM call")
        await message.answer(t("generic_error", lang))
