"""Answer rendering.

**Default path (plain text):** the model is asked to answer in plain prose, and
as a safety net we run the text through ``strip_markdown`` (so no stray ``#`` /
``*`` / ``_`` / backticks / ``>`` ever reach the chat) and ``split_plain`` it
into <=4096-char messages on logical boundaries (paragraph → sentence → word,
never mid-word). No file is produced.

**Explicit path (only when the user asks for "markdown"/"formatting"/"a file"):**
``to_html`` / ``html_chunks`` render Telegram HTML (vetted markdown→entities via
telegramify-markdown → aiogram html_decoration), or the raw text is sent as a
``.md`` file.

Pure functions (no Telegram I/O), so trivially unit-testable.
"""

from __future__ import annotations

import logging
import re

import telegramify_markdown
from aiogram.utils.text_decorations import html_decoration

from bot.output import TELEGRAM_MESSAGE_LIMIT, _split_text

logger = logging.getLogger(__name__)


# --- Plain-text stripper (default safety net) ----------------------------
_FENCE = re.compile(r"```[^\n]*\n?(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_BOLD_U = re.compile(r"__([^_]+)__")
_ITALIC_U = re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)")
_STRIKE = re.compile(r"~~([^~]+)~~")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_QUOTE = re.compile(r"^\s{0,3}>\s?")
_HR = re.compile(r"^\s*([-*_])\1{2,}\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+")
_MULTINL = re.compile(r"\n{3,}")


def strip_markdown(text: str) -> str:
    """Convert any Markdown in `text` to clean plain prose (UTF-8 preserved).

    Unwraps emphasis/code/links, turns headings into plain lines and bullets into
    "• ", drops fences/rules, and removes leftover ``*`` / `` ` `` markers. Intra-
    word underscores (e.g. file_name) are left intact.
    """
    if not text:
        return ""
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    s = _FENCE.sub(lambda m: m.group(1), s)      # ```code``` -> code
    s = _INLINE_CODE.sub(r"\1", s)               # `code` -> code
    s = _IMAGE.sub(r"\1", s)                      # ![alt](url) -> alt
    s = _LINK.sub(r"\1 (\2)", s)                 # [t](u) -> t (u)
    s = _BOLD.sub(r"\1", s)
    s = _BOLD_U.sub(r"\1", s)
    s = _STRIKE.sub(r"\1", s)
    s = _ITALIC_U.sub(r"\1", s)

    lines: list[str] = []
    for line in s.split("\n"):
        if _HR.match(line):
            lines.append("")
            continue
        line = _HEADING.sub("", line)
        line = _QUOTE.sub("", line)
        line = _BULLET.sub(r"\1• ", line)
        line = line.replace("`", "").replace("*", "")  # any stray emphasis markers
        lines.append(line.rstrip())
    s = "\n".join(lines)
    s = _MULTINL.sub("\n\n", s)
    return s.strip()


# --- Logical splitter (default) ------------------------------------------
_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.!?…。！？])\s+")


def split_plain(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split `text` into <=limit chunks on logical boundaries.

    Paragraph (blank line) → sentence → word; a single word longer than `limit`
    is hard-split as a last resort. Never cuts a word otherwise.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    units: list[str] = []  # each <= limit; packed into messages below
    for para in (p.strip() for p in _PARA.split(text)):
        if not para:
            continue
        if len(para) <= limit:
            units.append(para)
        else:
            units.extend(_split_long_paragraph(para, limit))
    return _pack(units, limit, "\n\n")


def _split_long_paragraph(para: str, limit: int) -> list[str]:
    sentences: list[str] = []
    for sent in _SENT.split(para):
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) <= limit:
            sentences.append(sent)
        else:
            sentences.extend(_pack(sent.split(" "), limit, " "))  # word-level
    return _pack(sentences, limit, " ")


def _pack(units: list[str], limit: int, sep: str) -> list[str]:
    """Greedily join `units` with `sep` into <=limit chunks (hard-split a unit
    only if it alone exceeds `limit`)."""
    chunks: list[str] = []
    cur = ""
    for unit in units:
        if not unit:
            continue
        candidate = unit if not cur else f"{cur}{sep}{unit}"
        if len(candidate) <= limit:
            cur = candidate
            continue
        if cur:
            chunks.append(cur)
            cur = ""
        if len(unit) <= limit:
            cur = unit
        else:  # pathological single token > limit
            for i in range(0, len(unit), limit):
                part = unit[i:i + limit]
                if len(part) == limit:
                    chunks.append(part)
                else:
                    cur = part
    if cur:
        chunks.append(cur)
    return chunks


# --- Explicit-request detection ------------------------------------------
_FILE_WORDS = ("файл", "файлом", "файлік", "file", ".md", "документ", "document")
_FORMAT_WORDS = (
    "markdown", "разметк", "розмітк", "форматир", "формат", "formatting",
    "formatted", "format",
)


def wants_file(instruction: str | None) -> bool:
    low = (instruction or "").lower()
    return any(w in low for w in _FILE_WORDS)


def wants_formatting(instruction: str | None) -> bool:
    low = (instruction or "").lower()
    return any(w in low for w in _FORMAT_WORDS)


# --- Explicit formatted path (HTML) --------------------------------------
_CODE_LANG = re.compile(r'<code language="(language-[^"]*)">')


def to_html(text: str) -> tuple[str, str]:
    """Render markdown `text` to (telegram_html, plain_text) for the explicit
    "with formatting" path. Plain text is the parse_mode=None fallback."""
    try:
        plain, entities = telegramify_markdown.convert(text)
        html = html_decoration.unparse(plain, entities)
        html = _CODE_LANG.sub(r'<code class="\1">', html)
        return html, plain
    except Exception:  # noqa: BLE001
        logger.exception("HTML rendering failed; falling back to plain text")
        return text, text


def html_chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[tuple[str, str]]:
    """Render to HTML and split into <=limit (html, plain) chunks on boundaries."""
    html, plain = to_html(text)
    if len(html) <= limit:
        return [(html, plain)]
    out: list[tuple[str, str]] = []
    for piece in _split_text(text, max(limit // 2, 1)) or [text]:
        p_html, p_plain = to_html(piece)
        if len(p_html) <= limit:
            out.append((p_html, p_plain))
        else:
            for raw in _split_text(p_plain, limit) or [p_plain[:limit]]:
                out.append((raw, raw))
    return out
