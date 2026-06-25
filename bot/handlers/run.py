"""Shared helpers: the actions keyboard and the rate-limited LLM text call.

Used by the actions handler and the custom-prompt handler so the guardrail /
call / output logic lives in one place.
"""

from __future__ import annotations

import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.output import send_result
from bot.prompts import KEYBOARD_ORDER, label_key
from bot.runtime import AppContext
from bot.services.openrouter import OpenRouterError
from bot.texts import t

logger = logging.getLogger(__name__)

# Callback data prefix for action buttons, e.g. "act:summary".
ACTION_CB_PREFIX = "act:"


class CustomStates(StatesGroup):
    """FSM for the custom-prompt flow."""

    waiting_for_instruction = State()  # user is typing their instruction
    waiting_for_context = State()      # bot asked whether to attach context


def build_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Inline keyboard with all actions, labels localized via texts.py."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in KEYBOARD_ORDER:
        row.append(
            InlineKeyboardButton(
                text=t(label_key(key), lang), callback_data=f"{ACTION_CB_PREFIX}{key}"
            )
        )
        if len(row) == 2:  # two buttons per row reads well on phones
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def run_llm(
    message: Message,
    ctx: AppContext,
    user_id: int,
    lang: str,
    system_prompt: str,
    user_content: str,
    show_keyboard: bool = True,
) -> None:
    """Apply the daily LLM limit, call the text model, and send the result."""
    if not await check_llm_limit(message, ctx, user_id, lang):
        return

    thinking = await message.answer(t("thinking", lang))
    try:
        answer = await ctx.orclient.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
        )
        ctx.limiter.record_llm(user_id)
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


async def check_llm_limit(message: Message, ctx: AppContext, user_id: int, lang: str) -> bool:
    """Return True if the user may make another LLM call; else notify and False."""
    allowed, reset_in = ctx.limiter.check_llm(user_id)
    if allowed:
        return True
    hours = max(1, round(reset_in / 3600))
    await message.answer(
        t("rate_limit_llm", lang).format(limit=ctx.settings.max_llm_calls_per_day, hours=hours)
    )
    return False
