"""Turn the model's raw markdown into clean, Telegram-ready output.

The model answers in Markdown (## headings, **bold**, lists, `code`, links…).
Sending that with ``parse_mode=None`` shows the literal syntax, so we render it
to Telegram's **HTML** subset and send with ``parse_mode=HTML``:

  markdown --[telegramify-markdown.convert]--> (plain text, Telegram entities)
           --[aiogram html_decoration.unparse]--> safe HTML (<b>,<i>,<code>,<pre>,
           <a>,<blockquote>,<s>,<u>…)

Both halves are vetted libraries (no fragile hand-rolled regex), Unicode/Cyrillic
safe. Each function also returns the matching plain text so a caller can resend
with ``parse_mode=None`` if Telegram ever rejects the HTML (400).

This module is pure (no Telegram I/O), so it is trivially unit-testable.
"""

from __future__ import annotations

import logging
import re

import telegramify_markdown
from aiogram.utils.text_decorations import html_decoration

from bot.output import TELEGRAM_MESSAGE_LIMIT, _split_text

logger = logging.getLogger(__name__)

# aiogram renders code-block language as ``<code language="language-x">`` but
# Telegram's documented HTML uses ``class="language-x"``. Normalise so code
# blocks don't trip a needless plain-text fallback.
_CODE_LANG = re.compile(r'<code language="(language-[^"]*)">')


def to_html(text: str) -> tuple[str, str]:
    """Render markdown `text` to (telegram_html, plain_text).

    `plain_text` is the same content with the markup stripped — the exact string
    to resend with ``parse_mode=None`` if Telegram rejects the HTML.
    """
    try:
        plain, entities = telegramify_markdown.convert(text)
        html = html_decoration.unparse(plain, entities)
        html = _CODE_LANG.sub(r'<code class="\1">', html)
        return html, plain
    except Exception:  # noqa: BLE001 - any converter failure -> plain passthrough
        logger.exception("HTML rendering failed; falling back to plain text")
        return text, text


def html_chunks(
    text: str, limit: int = TELEGRAM_MESSAGE_LIMIT
) -> list[tuple[str, str]]:
    """Render to HTML and split into <=limit (html, plain) chunks on boundaries.

    Splitting happens on the *source* text (line/paragraph boundaries) and each
    piece is rendered independently, so a chunk's HTML tags are always balanced
    (a split never lands inside a tag). The common case (one chunk) is fast.
    """
    html, plain = to_html(text)
    if len(html) <= limit:
        return [(html, plain)]

    out: list[tuple[str, str]] = []
    for piece in _split_text(text, max(limit // 2, 1)) or [text]:
        p_html, p_plain = to_html(piece)
        if len(p_html) <= limit:
            out.append((p_html, p_plain))
        else:  # pathological: ship this piece as plain, hard-split to size
            for raw in _split_text(p_plain, limit) or [p_plain[:limit]]:
                out.append((raw, raw))
    return out


def plain_chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split raw text into <=limit chunks on line/paragraph boundaries."""
    return _split_text(text, limit) or [text[:limit]]
