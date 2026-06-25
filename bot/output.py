"""Shared helpers for sending LLM results back to Telegram.

Output strategy (prefer chat messages over files):
  * answer <= one message -> send as a single plain-text message,
  * longer -> split into multiple plain-text messages on line boundaries,
  * only very long answers fall back to a .md file attachment.

Everything is sent with parse_mode=None so raw LLM output (which often contains
stray *, _, `, [] markdown) never triggers a Telegram parse error.
"""

from __future__ import annotations

from aiogram.types import BufferedInputFile, Message

from bot import texts

# Telegram hard limit for a single text message.
TELEGRAM_MESSAGE_LIMIT = 4096
# Above this many characters, or more than this many message chunks, we send a
# file instead of flooding the chat.
FILE_THRESHOLD_CHARS = 12000
MAX_MESSAGE_CHUNKS = 4


async def send_result(message: Message, text: str) -> None:
    """Send `text`, preferring chat messages and falling back to a file."""
    text = text.strip() or "—"

    # Fits in one message -> just send it.
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        await message.answer(text, parse_mode=None)
        return

    chunks = _split_text(text, TELEGRAM_MESSAGE_LIMIT)

    # Very long -> attach as a Markdown file (UTF-8) plus a short heads-up.
    if len(text) > FILE_THRESHOLD_CHARS or len(chunks) > MAX_MESSAGE_CHUNKS:
        document = BufferedInputFile(text.encode("utf-8"), filename=texts.RESULT_FILENAME)
        await message.answer_document(document, caption=texts.LONG_RESULT_HEADS_UP)
        return

    # Otherwise send the chunks in order as plain-text messages.
    for chunk in chunks:
        await message.answer(chunk, parse_mode=None)


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into <= limit chunks, breaking on line boundaries.

    Lines are rejoined into buffers up to `limit`; a single line longer than
    `limit` is hard-split. Blank lines are preserved, so paragraph boundaries
    are respected naturally.
    """
    # Break into atomic units no larger than `limit` (hard-split long lines).
    units: list[str] = []
    for line in text.split("\n"):
        if len(line) <= limit:
            units.append(line)
        else:
            for i in range(0, len(line), limit):
                units.append(line[i:i + limit])

    chunks: list[str] = []
    buf = ""
    for unit in units:
        candidate = unit if not buf else f"{buf}\n{unit}"
        if len(candidate) <= limit:
            buf = candidate
        else:
            chunks.append(buf)
            buf = unit
    if buf:
        chunks.append(buf)
    return chunks
