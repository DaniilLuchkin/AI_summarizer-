"""Shared helpers: the actions keyboard and the rate-limited LLM call.

Used by both the predefined-actions handler and the custom-prompt handler so
the guardrail / call / output logic lives in exactly one place.
"""

from __future__ import annotations

import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import texts
from bot.output import send_result
from bot.prompts import ACTIONS, CUSTOM_KEY, CUSTOM_LABEL
from bot.runtime import AppContext
from bot.services.openrouter import OpenRouterError

logger = logging.getLogger(__name__)

# Callback data prefix for action buttons, e.g. "act:summary".
ACTION_CB_PREFIX = "act:"


class CustomStates(StatesGroup):
    """FSM: waiting for the user's free-text instruction (+ optional context)."""

    waiting_for_instruction = State()


def build_actions_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with all predefined actions + the custom-prompt button."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for action in ACTIONS:
        row.append(
            InlineKeyboardButton(
                text=action.label, callback_data=f"{ACTION_CB_PREFIX}{action.key}"
            )
        )
        if len(row) == 2:  # two buttons per row keeps it readable on phones
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text=CUSTOM_LABEL, callback_data=f"{ACTION_CB_PREFIX}{CUSTOM_KEY}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def run_llm(
    message: Message,
    ctx: AppContext,
    user_id: int,
    system_prompt: str,
    user_content: str,
    show_keyboard: bool = True,
) -> None:
    """Apply the daily LLM rate limit, call the model, and send the result.

    Errors are caught and reported in Russian so the polling loop never dies.
    """
    allowed, reset_in = ctx.limiter.check_llm(user_id)
    if not allowed:
        hours = max(1, round(reset_in / 3600))
        await message.answer(
            texts.RATE_LIMIT_LLM.format(limit=ctx.settings.max_llm_calls_per_day, hours=hours)
        )
        return

    thinking = await message.answer(texts.THINKING)
    try:
        answer = await ctx.orclient.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
        )
        ctx.limiter.record_llm(user_id)
        await send_result(message, answer)
        if show_keyboard:
            await message.answer(texts.FOLLOWUP_HINT, reply_markup=build_actions_keyboard())
    except OpenRouterError:
        logger.exception("LLM call failed")
        await message.answer(texts.LLM_ERROR)
    except Exception:  # noqa: BLE001 - never crash the polling loop
        logger.exception("Unexpected error during LLM call")
        await message.answer(texts.GENERIC_ERROR)
    finally:
        # Best-effort cleanup of the "thinking…" placeholder.
        try:
            await thinking.delete()
        except Exception:  # noqa: BLE001
            pass
