"""Shared helpers: FSM states, keyboards, and the rate-limited LLM text call."""

from __future__ import annotations

import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.output import send_result
from bot.prompts import CUSTOM_KEY, KEYBOARD_ORDER, label_key
from bot.runtime import AppContext
from bot.services.openrouter import OpenRouterError
from bot.texts import t

logger = logging.getLogger(__name__)

# Callback data prefixes / constants.
ACTION_CB_PREFIX = "act:"   # act:<key> — stage a predefined action or custom
RUN_CB = "run:now"          # run the staged action without added context


class ActionStates(StatesGroup):
    """A predefined action (or custom) is staged, awaiting optional context."""

    awaiting_input = State()  # FSM data holds {"action_key": <key>}


def build_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Predefined actions in a 2-per-row grid, custom button full-width at bottom."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in KEYBOARD_ORDER:
        if key == CUSTOM_KEY:
            continue  # custom gets its own full-width bottom row
        row.append(
            InlineKeyboardButton(
                text=t(label_key(key), lang), callback_data=f"{ACTION_CB_PREFIX}{key}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    # Bottom-most, full-width "or just type your prompt ⬇️" button.
    rows.append(
        [
            InlineKeyboardButton(
                text=t(label_key(CUSTOM_KEY), lang),
                callback_data=f"{ACTION_CB_PREFIX}{CUSTOM_KEY}",
            )
        ]
    )
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
) -> None:
    """Call the text model and send the result.

    Quota gating happens in execute.run_staged before calling this. `model` /
    `api_key` support the Pro model and bring-your-own-key.
    """
    thinking = await message.answer(t("thinking", lang))
    try:
        answer = await ctx.orclient.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=model,
            api_key=api_key,
        )
        await send_result(message, answer, lang)
        if show_keyboard:
            await message.answer(t("followup_hint", lang), reply_markup=build_actions_keyboard(lang))
    except OpenRouterError:
        logger.exception("LLM call failed")
        await message.answer(t("llm_error", lang))
    except Exception:  # noqa: BLE001 - never crash the polling loop
        logger.exception("Unexpected error during LLM call")
        await message.answer(t("generic_error", lang))
    finally:
        try:
            await thinking.delete()
        except Exception:  # noqa: BLE001
            pass
