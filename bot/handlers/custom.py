"""Custom-prompt FSM.

Flow:
  1. User taps "✍️ Custom prompt" -> state = waiting_for_instruction.
  2. User types the instruction -> we ask whether to add context, with inline
     buttons "📎 Attach" / "▶️ Send"  (state = waiting_for_context).
  3a. "▶️ Send"   -> run the prompt with no extra context.
  3b. "📎 Attach" -> ask for a file/link; the next message is parsed as context.
      (Sending a file/link directly in this state also works.)

After answering we drop to the default state but keep the batch active.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.handlers.run import CustomStates, run_llm
from bot.prompts import CUSTOM_SYSTEM
from bot.runtime import AppContext
from bot.services import context as context_service
from bot.services import media
from bot.services.media import FileTooLarge
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)

# Don't fetch an unbounded number of links from one message.
MAX_LINKS = 3
CTX_CB_PREFIX = "ctx:"


def build_router(ctx: AppContext) -> Router:
    router = Router(name="custom")

    def _lang(message: Message) -> str:
        chat_state = ctx.store.get(message.chat.id)
        return chat_state.lang if chat_state else resolve_lang(message.from_user.language_code)

    # --- Step 2: collect the instruction --------------------------------
    @router.message(CustomStates.waiting_for_instruction)
    async def on_instruction(message: Message, state: FSMContext) -> None:
        lang = _lang(message)
        chat_state = ctx.store.get(message.chat.id)
        if chat_state is None or not chat_state.has_active_batch:
            await state.clear()
            await message.answer(t("no_active_batch", lang))
            return

        instruction = (message.text or message.caption or "").strip()
        if not instruction:
            await message.answer(t("custom_prompt_empty", lang))
            return

        await state.update_data(instruction=instruction)
        await state.set_state(CustomStates.waiting_for_context)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_attach", lang), callback_data=f"{CTX_CB_PREFIX}attach")],
                [InlineKeyboardButton(text=t("btn_send", lang), callback_data=f"{CTX_CB_PREFIX}send")],
            ]
        )
        await message.answer(t("custom_add_context_q", lang), reply_markup=keyboard)

    # --- Step 3a/3b: the context choice buttons -------------------------
    @router.callback_query(CustomStates.waiting_for_context, F.data.startswith(CTX_CB_PREFIX))
    async def on_context_choice(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        message = callback.message
        if message is None:
            return
        lang = _lang(message)
        choice = callback.data[len(CTX_CB_PREFIX):]

        if choice == "send":
            data = await state.get_data()
            await _run_custom(
                ctx, message, callback.from_user.id, state, lang, data.get("instruction", ""), []
            )
        elif choice == "attach":
            # Stay in waiting_for_context; the next message is the payload.
            await message.answer(t("custom_send_context", lang))

    # --- Step 3b payload: a file and/or a link --------------------------
    @router.message(CustomStates.waiting_for_context)
    async def on_context_payload(message: Message, state: FSMContext, bot: Bot) -> None:
        lang = _lang(message)
        data = await state.get_data()
        instruction = data.get("instruction", "")
        context_parts = await _collect_context(ctx, bot, message, lang)
        if not context_parts:
            await message.answer(t("context_none_found", lang))
        await _run_custom(ctx, message, message.from_user.id, state, lang, instruction, context_parts)

    return router


async def _run_custom(
    ctx: AppContext,
    message: Message,
    user_id: int,
    state: FSMContext,
    lang: str,
    instruction: str,
    context_parts: list[str],
) -> None:
    chat_state = ctx.store.get(message.chat.id)
    if chat_state is None or not chat_state.has_active_batch:
        await state.clear()
        await message.answer(t("no_active_batch", lang))
        return

    await state.clear()  # back to default; batch stays active for follow-ups
    document, truncated = ctx.store.assemble_for_llm(chat_state)
    if truncated:
        await message.answer(t("context_truncated", lang))

    user_content = _build_user_content(document, instruction, context_parts)
    await run_llm(message, ctx, user_id, lang, CUSTOM_SYSTEM, user_content)


async def _collect_context(
    ctx: AppContext, bot: Bot, message: Message, lang: str
) -> list[str]:
    """Fetch links found in the message and parse any attached document."""
    parts: list[str] = []
    text = (message.text or message.caption or "")

    for url in context_service.extract_urls(text)[:MAX_LINKS]:
        try:
            fetched = await context_service.fetch_link(
                url, ctx.settings.link_fetch_timeout, ctx.settings.context_max_chars
            )
            if fetched:
                parts.append(f"Context from link {url}:\n{fetched}")
                await message.answer(t("context_added_link", lang))
        except Exception as exc:  # noqa: BLE001 - report and keep going
            logger.warning("Link fetch failed for %s: %s", url, exc)
            await message.answer(t("context_link_failed", lang).format(url=url, error=exc))

    if message.document:
        name = message.document.file_name or "file"
        try:
            data = await media.download(bot, message.document.file_id)
            parsed = context_service.parse_file(name, data, ctx.settings.context_max_chars)
            if parsed:
                parts.append(f"Context from file «{name}»:\n{parsed}")
                await message.answer(t("context_added_file", lang).format(name=name))
        except FileTooLarge:
            await message.answer(
                t("context_file_failed", lang).format(name=name, error=">20MB")
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("File parse failed for %s: %s", name, exc)
            await message.answer(t("context_file_failed", lang).format(name=name, error=exc))

    return parts


def _build_user_content(document: str, instruction: str, context_parts: list[str]) -> str:
    """Assemble the final user message: batch + instruction + extra context."""
    blocks = [
        "=== MESSAGE BATCH ===",
        document,
        "",
        "=== USER INSTRUCTION ===",
        instruction or "(no explicit instruction — act sensibly)",
    ]
    if context_parts:
        blocks.append("")
        blocks.append("=== ADDITIONAL CONTEXT ===")
        blocks.extend(context_parts)
    return "\n".join(blocks)
