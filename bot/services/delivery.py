"""Deliver a model text answer: live streaming -> plain-text messages.

One entry point, ``deliver_answer``, used by the private and group handlers.

Flow
----
1. If streaming is on, stream the SSE deltas from OpenRouter and push the
   growing plain-text preview with ``sendMessageDraft`` (Bot API 9.3+, throttled
   ~1/sec). The draft is an ephemeral ~30s preview.
2. If ``sendMessageDraft`` isn't supported, fall back to a placeholder message
   that is live-edited (``editMessageText``, same throttle).
3. On finish the answer is *persisted* as real message(s). DEFAULT: markdown is
   stripped and the text is smart-split into <=4096-char plain messages on
   logical boundaries (no file). Only when the user explicitly asked do we send
   a formatted HTML message (``formatted``) or a raw ``.md`` file (``as_file``).

Exactly one result is persisted; the ephemeral draft never remains as the final
answer. Every "new" API path is wrapped so an unsupported method or a parse
rejection cleanly drops to the next fallback instead of erroring the handler.
"""

from __future__ import annotations

import itertools
import logging
import time

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import BufferedInputFile, Message

from bot import texts
from bot.output import TELEGRAM_MESSAGE_LIMIT
from bot.runtime import AppContext
from bot.services import render
from bot.texts import t

logger = logging.getLogger(__name__)

# Process-wide capability flag for sendMessageDraft: None=unknown, then set once
# (one failed round-trip is enough — don't probe it on every answer).
_draft_supported: bool | None = None
# Monotonic counter for draft ids (each streamed answer gets a fresh draft).
_draft_counter = itertools.count(1)


async def deliver_answer(
    message: Message,
    ctx: AppContext,
    lang: str,
    messages: list[dict],
    *,
    model: str | None = None,
    api_key: str | None = None,
    formatted: bool = False,
    as_file: bool = False,
) -> None:
    """Run the chat call (streaming if enabled) and deliver the answer.

    Default: clean plain text, smart-split into several messages. `formatted` /
    `as_file` (set only when the user explicitly asks) switch to a formatted HTML
    message or a raw ``.md`` file. Raises ``OpenRouterError`` on model failure so
    callers keep their existing error handling.
    """
    s = ctx.settings
    placeholder: Message | None = None
    try:
        if s.streaming_enabled:
            full, placeholder = await _stream(message, ctx, lang, messages, model, api_key)
        else:
            placeholder = await message.answer(t("thinking", lang))
            full = await ctx.orclient.chat(messages, model=model, api_key=api_key)
    except Exception:
        await _safe_delete(placeholder)
        raise

    full = (full or "").strip() or "—"
    await _finalize(message, full, lang, placeholder, formatted=formatted, as_file=as_file)


# --- Streaming -----------------------------------------------------------
async def _stream(
    message: Message, ctx: AppContext, lang: str, messages, model, api_key
) -> tuple[str, Message | None]:
    """Stream deltas, showing progress via a draft (or an edited placeholder).

    Returns (full_text, placeholder) where ``placeholder`` is the live-edited
    message when the draft path is unavailable, else None (draft path).
    """
    global _draft_supported
    s = ctx.settings
    throttle = max(s.stream_throttle_ms, 0) / 1000.0
    draft_id = next(_draft_counter)

    use_draft = _draft_supported is not False
    placeholder: Message | None = None
    # Immediate feedback + a one-shot probe of draft support.
    if use_draft and not await _try_draft(message, draft_id, t("thinking", lang)):
        use_draft = False
        _draft_supported = False
    if not use_draft:
        placeholder = await message.answer(t("thinking", lang))

    full = ""
    last_edit = time.monotonic()
    async for delta in ctx.orclient.chat_stream(messages, model=model, api_key=api_key):
        full += delta
        now = time.monotonic()
        if now - last_edit < throttle or not full.strip():
            continue
        preview = full[:TELEGRAM_MESSAGE_LIMIT]  # plain-text live preview
        if use_draft:
            if await _try_draft(message, draft_id, preview):
                _draft_supported = True
            else:  # lost draft support mid-stream -> switch to edit placeholder
                use_draft = False
                _draft_supported = False
                placeholder = await message.answer(preview)
        else:
            try:
                await placeholder.edit_text(preview, parse_mode=None)
            except TelegramBadRequest:
                pass  # "not modified" / transient -> skip this tick
        last_edit = now

    return full, placeholder


async def _try_draft(message: Message, draft_id: int, text: str) -> bool:
    """Best-effort ``sendMessageDraft``. False if the method/feature is absent."""
    try:
        await message.bot.send_message_draft(
            chat_id=message.chat.id, draft_id=draft_id, text=text[:TELEGRAM_MESSAGE_LIMIT]
        )
        return True
    except (TelegramAPIError, TypeError, AttributeError) as exc:
        logger.info("sendMessageDraft unavailable; using edit-streaming (%s)", exc)
        return False
    except Exception:  # noqa: BLE001 - never let streaming crash the handler
        logger.info("sendMessageDraft failed; using edit-streaming", exc_info=True)
        return False


# --- Final persisted delivery -------------------------------------------
async def _finalize(
    message: Message,
    text: str,
    lang: str,
    placeholder: Message | None,
    *,
    formatted: bool,
    as_file: bool,
) -> None:
    # Explicit ".md file" request: send the raw answer as a file (any length).
    if as_file:
        await _safe_delete(placeholder)
        document = BufferedInputFile(text.encode("utf-8"), filename=texts.RESULT_FILENAME)
        await message.answer_document(document, caption=t("result_file_caption", lang))
        return
    # Explicit "with formatting / markdown" request: clean Telegram HTML.
    if formatted:
        await _send_html(message, text, placeholder)
        return
    # DEFAULT: plain prose, markdown stripped, smart-split into several messages.
    chunks = render.split_plain(render.strip_markdown(text)) or ["—"]
    await _send_plain(message, chunks, placeholder)


async def _send_plain(message: Message, chunks: list[str], placeholder: Message | None) -> None:
    """Send plain-text chunks; reuse the streaming placeholder as the first one."""
    first = True
    for chunk in chunks:
        if first and placeholder is not None:
            first = False
            try:
                await placeholder.edit_text(chunk, parse_mode=None)
                continue
            except TelegramBadRequest:
                await _safe_delete(placeholder)  # unchanged/too-old -> send fresh
        first = False
        await message.answer(chunk, parse_mode=None)


async def _send_html(message: Message, text: str, placeholder: Message | None) -> None:
    """Send the answer as clean HTML; resend a chunk as plain text on a 400."""
    for i, (html, plain) in enumerate(render.html_chunks(text)):
        first = i == 0 and placeholder is not None
        try:
            if first:
                await placeholder.edit_text(html, parse_mode=ParseMode.HTML)
            else:
                await message.answer(html, parse_mode=ParseMode.HTML)
        except TelegramBadRequest:
            # Telegram rejected the markup -> same text, no formatting.
            try:
                if first:
                    await placeholder.edit_text(plain, parse_mode=None)
                else:
                    await message.answer(plain, parse_mode=None)
            except TelegramBadRequest:
                logger.warning("Dropped a chunk Telegram refused even as plain text")


async def _safe_delete(msg: Message | None) -> None:
    if msg is None:
        return
    try:
        await msg.delete()
    except Exception:  # noqa: BLE001
        pass
