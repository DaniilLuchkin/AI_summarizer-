"""Turn the model's raw markdown into clean, Telegram-ready output.

The model answers in Markdown (## headings, **bold**, lists, `code`, links…).
Sending that with ``parse_mode=None`` shows the literal syntax, so we render it:

  1. **Rich message** (Bot API ``sendRichMessage``) — best-effort, native
     rendering. Built here as an ``InputRichMessage``; the *send* attempt and
     its fallback live in ``services.delivery`` (the method may be unsupported).
  2. **MarkdownV2** — produced by ``telegramify-markdown``, a vetted converter
     that escapes correctly (no fragile hand-rolled regex) and preserves
     Unicode/Cyrillic. Split into <=4096-char chunks on safe boundaries.
  3. **Plain text** — the ultimate fallback if Telegram rejects the markup.

This module is pure (no Telegram I/O), so it is trivially unit-testable.
"""

from __future__ import annotations

import logging

import telegramify_markdown
from aiogram.types import InputRichMessage

from bot.output import TELEGRAM_MESSAGE_LIMIT, _split_text

logger = logging.getLogger(__name__)


def markdownv2_chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Render `text` to MarkdownV2 and split into valid <=limit chunks.

    ``telegramify-markdown`` guarantees the escaping and the split never breaks
    an entity (it is entity-aware), so each chunk is independently parseable.
    Falls back to a single plain-split list if the converter ever errors.
    """
    try:
        md = telegramify_markdown.markdownify(text)
        chunks = telegramify_markdown.split_markdownv2(md, max_utf16_len=limit)
        # Defensive: drop empties, guarantee the contract (every chunk <= limit).
        out = [c for c in chunks if c.strip()]
        if out and all(len(c) <= limit for c in out):
            return out
    except Exception:  # noqa: BLE001 - any converter failure -> plain split
        logger.exception("MarkdownV2 rendering failed; falling back to plain")
    return plain_chunks(text, limit)


def plain_chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split raw text into <=limit chunks on line/paragraph boundaries."""
    return _split_text(text, limit) or [text[:limit]]


def build_rich(text: str) -> InputRichMessage | None:
    """Build an ``InputRichMessage`` (HTML body) for a best-effort rich send.

    Returns None if the converter can't produce one. The caller wraps the actual
    ``sendRichMessage`` call so an unsupported method degrades to MarkdownV2.
    """
    try:
        rich = telegramify_markdown.richify(text, mode="html")
        if getattr(rich, "html", None):
            return InputRichMessage(html=rich.html)
        if getattr(rich, "markdown", None):
            return InputRichMessage(markdown=rich.markdown)
    except Exception:  # noqa: BLE001
        logger.debug("Rich message build failed", exc_info=True)
    return None
