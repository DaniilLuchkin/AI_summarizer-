"""Shared helpers: FSM states, keyboards, and the rate-limited LLM text call."""

from __future__ import annotations

import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.prompts import CUSTOM_KEY, PRIMARY_ACTION_KEYS, TEMPLATES, label_key
from bot.runtime import AppContext
from bot.services.credits import fmt
from bot.services.delivery import deliver_answer
from bot.services.openrouter import OpenRouterError
from bot.texts import t

logger = logging.getLogger(__name__)

# Callback data prefixes / constants.
ACTION_CB_PREFIX = "act:"   # act:<key> — stage a predefined action or custom
RUN_CB = "run:now"          # run the staged action without added context
UPGRADE_CB = "upgrade"      # open the Pro purchase options (handled in billing)
BUY_CB = "buy:open"         # open the Buy-credits packs (handled in billing)
RETRY_CB = "retry:llm"      # re-run the chat's last LLM call after an error
TPL_OPEN_CB = "tpl:open"    # show the freelancer-template submenu (in place)
TPL_BACK_CB = "tpl:back"    # return from templates to the action grid
TPL_CB_PREFIX = "tpl:"      # tpl:<key> — run a packaged template prompt

# Warn once when the combined balance drops below this many tenths (5.0 credits).
LOW_BALANCE_TENTHS = 50


def build_upgrade_keyboard(lang: str) -> InlineKeyboardMarkup:
    """One-tap "⭐ Upgrade to Pro" button, attached to paywall/limit replies."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn_upgrade", lang), callback_data=UPGRADE_CB)]]
    )


def build_credits_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Buy-credits + Upgrade buttons, shown whenever a user is out of credits."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_buy_credits", lang), callback_data=BUY_CB)],
            [InlineKeyboardButton(text=t("btn_upgrade", lang), callback_data=UPGRADE_CB)],
        ]
    )


def build_retry_keyboard(lang: str) -> InlineKeyboardMarkup:
    """One-tap 🔄 Retry, attached to LLM error messages."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn_retry", lang), callback_data=RETRY_CB)]]
    )


class ActionStates(StatesGroup):
    """A predefined action (or custom) is staged, awaiting optional context."""

    awaiting_input = State()  # FSM data holds {"action_key": <key>}


def build_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    """The text-action grid (2 per row) + Templates + the full-width Custom button."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in PRIMARY_ACTION_KEYS:
        row.append(InlineKeyboardButton(
            text=t(label_key(key), lang), callback_data=f"{ACTION_CB_PREFIX}{key}"
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t("btn_templates", lang), callback_data=TPL_OPEN_CB)])
    rows.append(
        [InlineKeyboardButton(
            text=t(label_key(CUSTOM_KEY), lang), callback_data=f"{ACTION_CB_PREFIX}{CUSTOM_KEY}"
        )]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_templates_keyboard(lang: str) -> InlineKeyboardMarkup:
    """The freelancer-template submenu (one per row) + Back."""
    rows = [
        [InlineKeyboardButton(text=t(f"tpl_{key}", lang), callback_data=f"{TPL_CB_PREFIX}{key}")]
        for key in TEMPLATES
    ]
    rows.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data=TPL_BACK_CB)])
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
    user_id: int | None = None,
    charge_text: bool = False,
) -> None:
    """Call the text model and deliver the (streamed) result as plain text.

    Balance is soft-checked in execute.run_staged before calling this. When
    `charge_text` is set (non-BYO users), the token-based text cost is charged
    AFTER a successful response. `formatted` / `as_file` are set only when the
    user explicitly asked for formatting / a file.
    """
    # Remember the run so the 🔄 Retry button can replay it after an error.
    chat_state = ctx.store.get(message.chat.id)
    if chat_state is not None:
        chat_state.last_run = {
            "system": system_prompt, "content": user_content,
            "formatted": formatted, "as_file": as_file,
        }
    try:
        tokens = await deliver_answer(
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
        if charge_text and user_id is not None and tokens > 0:
            # Tiny, generous cost; best-effort (already delivered).
            await ctx.credits.charge(user_id, ctx.credits.text_cost_tenths(tokens), "text")
            await _warn_low_balance(message, ctx, lang, user_id, chat_state)
        if show_keyboard:
            await message.answer(t("followup_hint", lang), reply_markup=build_actions_keyboard(lang))
    except OpenRouterError:
        logger.exception("LLM call failed")
        await message.answer(t("llm_error", lang), reply_markup=build_retry_keyboard(lang))
    except Exception:  # noqa: BLE001 - never crash the polling loop
        logger.exception("Unexpected error during LLM call")
        await message.answer(t("generic_error", lang), reply_markup=build_retry_keyboard(lang))


async def _warn_low_balance(message, ctx: AppContext, lang: str, user_id: int, chat_state) -> None:
    """One-shot heads-up (with buy buttons) when the balance runs low."""
    if chat_state is None or chat_state.low_balance_warned:
        return
    persistent, daily = await ctx.credits.balance(user_id)
    total = persistent + daily
    if 0 < total < LOW_BALANCE_TENTHS:
        chat_state.low_balance_warned = True
        await message.answer(
            t("credits_low_warning", lang).format(balance=fmt(total)),
            reply_markup=build_credits_keyboard(lang),
        )
