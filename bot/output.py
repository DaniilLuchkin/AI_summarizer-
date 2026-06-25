"""Shared helpers for sending LLM results back to Telegram."""

from __future__ import annotations

from aiogram.types import BufferedInputFile, Message

from bot import texts

# Telegram hard limit for a single text message.
TELEGRAM_MESSAGE_LIMIT = 4096


async def send_result(message: Message, text: str) -> None:
    """Send `text` as a normal message, or as a .md file if it's too long."""
    text = text.strip() or "—"
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        await message.answer(text)
        return

    # Long answer -> attach as a Markdown file plus a short heads-up.
    document = BufferedInputFile(text.encode("utf-8"), filename=texts.RESULT_FILENAME)
    await message.answer_document(document, caption=texts.LONG_RESULT_HEADS_UP)
