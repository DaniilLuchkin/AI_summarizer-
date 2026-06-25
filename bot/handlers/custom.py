"""Custom-prompt FSM: collect a free-text instruction + optional context.

The instruction message may also carry context in the SAME message:
  * a link (http/https URL) anywhere in the text/caption, and/or
  * an attached document (.pdf / .docx / .txt / .md).

Both are parsed to text and appended (clearly labeled) before the LLM call.
After answering, we drop back to the default state but keep the batch active,
so the user can immediately run more actions or another custom prompt.
"""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import texts
from bot.handlers.run import CustomStates, run_llm
from bot.prompts import CUSTOM_SYSTEM
from bot.runtime import AppContext
from bot.services import context as context_service
from bot.services import media
from bot.services.media import FileTooLarge

logger = logging.getLogger(__name__)

# Don't fetch an unbounded number of links from one message.
MAX_LINKS = 3


def build_router(ctx: AppContext) -> Router:
    router = Router(name="custom")

    @router.message(CustomStates.waiting_for_instruction)
    async def on_instruction(message: Message, state: FSMContext, bot: Bot) -> None:
        chat_state = ctx.store.get(message.chat.id)
        if chat_state is None or not chat_state.has_active_batch:
            await state.clear()
            await message.answer(texts.NO_ACTIVE_BATCH)
            return

        instruction = (message.text or message.caption or "").strip()
        if not instruction and not message.document:
            await message.answer(texts.CUSTOM_PROMPT_EMPTY)
            return

        context_parts = await _collect_context(ctx, bot, message, instruction)

        # Leave the FSM state now so follow-ups behave predictably.
        await state.clear()

        document, truncated = ctx.store.assemble_for_llm(chat_state)
        if truncated:
            await message.answer(texts.CONTEXT_TRUNCATED)

        user_content = _build_user_content(document, instruction, context_parts)
        await run_llm(
            message,
            ctx,
            user_id=message.from_user.id,
            system_prompt=CUSTOM_SYSTEM,
            user_content=user_content,
        )

    return router


async def _collect_context(
    ctx: AppContext, bot: Bot, message: Message, instruction: str
) -> list[str]:
    """Fetch links found in the instruction and parse any attached document."""
    parts: list[str] = []

    # --- Links -----------------------------------------------------------
    for url in context_service.extract_urls(instruction)[:MAX_LINKS]:
        try:
            text = await context_service.fetch_link(
                url, ctx.settings.link_fetch_timeout, ctx.settings.context_max_chars
            )
            if text:
                parts.append(f"Контекст по ссылке {url}:\n{text}")
                await message.answer(texts.CONTEXT_ADDED_LINK)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            logger.warning("Link fetch failed for %s: %s", url, exc)
            await message.answer(texts.CONTEXT_LINK_FAILED.format(url=url, error=exc))

    # --- Attached document ----------------------------------------------
    if message.document:
        name = message.document.file_name or "file"
        try:
            data = await media.download(bot, message.document.file_id)
            text = context_service.parse_file(name, data, ctx.settings.context_max_chars)
            if text:
                parts.append(f"Контекст из файла «{name}»:\n{text}")
                await message.answer(texts.CONTEXT_ADDED_FILE.format(name=name))
        except FileTooLarge:
            await message.answer(
                texts.CONTEXT_FILE_FAILED.format(name=name, error="файл больше 20 МБ")
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("File parse failed for %s: %s", name, exc)
            await message.answer(texts.CONTEXT_FILE_FAILED.format(name=name, error=exc))

    return parts


def _build_user_content(document: str, instruction: str, context_parts: list[str]) -> str:
    """Assemble the final user message: batch + instruction + extra context."""
    blocks = [
        "=== ПАЧКА СООБЩЕНИЙ ===",
        document,
        "",
        "=== ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ ===",
        instruction or "(инструкция не задана — действуй разумно)",
    ]
    if context_parts:
        blocks.append("")
        blocks.append("=== ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ===")
        blocks.extend(context_parts)
    return "\n".join(blocks)
