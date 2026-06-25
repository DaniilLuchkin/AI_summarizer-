"""Shared helpers for sending LLM text results back to Telegram.

Output strategy (prefer chat messages over files):
  * answer <= one message -> single plain-text message,
  * longer -> multiple plain-text messages split on line boundaries,
  * very long -> a .md file attachment (UTF-8).

parse_mode=None everywhere so raw LLM markdown never triggers a parse error.
"""

from __future__ import annotations

from aiogram.types import BufferedInputFile, Message

from bot import texts
from bot.texts import t

TELEGRAM_MESSAGE_LIMIT = 4096
FILE_THRESHOLD_CHARS = 12000
MAX_MESSAGE_CHUNKS = 4


async def send_result(message: Message, text: str, lang: str) -> None:
    """Send `text`, preferring chat messages and falling back to a file."""
    text = text.strip() or "—"

    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        await message.answer(text, parse_mode=None)
        return

    chunks = _split_text(text, TELEGRAM_MESSAGE_LIMIT)

    if len(text) > FILE_THRESHOLD_CHARS or len(chunks) > MAX_MESSAGE_CHUNKS:
        document = BufferedInputFile(text.encode("utf-8"), filename=texts.RESULT_FILENAME)
        await message.answer_document(document, caption=t("long_result_heads_up", lang))
        return

    for chunk in chunks:
        await message.answer(chunk, parse_mode=None)


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into <= limit chunks, breaking on line boundaries.

    A single line longer than `limit` is hard-split. Blank lines are preserved,
    so paragraph boundaries are respected naturally.
    """
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
