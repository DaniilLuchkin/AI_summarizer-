"""Deliver a model text answer: live streaming -> clean rendered final -> .md.

One entry point, ``deliver_answer``, replaces the old "thinking message + raw
``send_result``" flow used by the private and group handlers.

Flow
----
1. Post a placeholder ("🤔 …").
2. If streaming is on, stream the SSE deltas from OpenRouter and live-edit the
   placeholder (throttled). This is the reliable streaming mechanism: the new
   ``sendMessageDraft``/``sendRichMessageDraft`` methods exist in aiogram but
   need Telegram-side (business-connection) support we can't assume, so we use
   the always-working ``editMessageText`` live edit instead.
3. Render the final answer cleanly (rich -> MarkdownV2 -> plain) and persist it
   as real message(s) — the placeholder is reused as the first message so there
   is no flicker, and exactly one final answer is persisted.
4. Pro / BYO users additionally get the raw ``result.md`` attached.

Every "new" API path is wrapped so an unsupported method or a Telegram parse
rejection cleanly drops to the next fallback instead of erroring the handler.
"""

from __future__ import annotations

import logging
import time

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, Message

from bot import texts
from bot.output import FILE_THRESHOLD_CHARS, MAX_MESSAGE_CHUNKS, TELEGRAM_MESSAGE_LIMIT
from bot.runtime import AppContext
from bot.services import render
from bot.texts import t

logger = logging.getLogger(__name__)

# Process-wide capability flag: once sendRichMessage proves unsupported we stop
# trying it (one failed round-trip is enough; don't pay it on every answer).
_rich_supported: bool = True


async def deliver_answer(
    message: Message,
    ctx: AppContext,
    lang: str,
    messages: list[dict],
    *,
    model: str | None = None,
    api_key: str | None = None,
    attach_md: bool = False,
) -> None:
    """Run the chat call (streaming if enabled) and deliver a clean answer.

    Raises ``OpenRouterError`` on model failure so callers keep their existing
    error handling; send-side failures are handled here (fallback chain).
    """
    s = ctx.settings
    placeholder = await message.answer(t("thinking", lang))

    try:
        if s.streaming_enabled:
            full = await _stream_into(placeholder, ctx, lang, messages, model, api_key)
        else:
            full = await ctx.orclient.chat(messages, model=model, api_key=api_key)
    except Exception:
        await _safe_delete(placeholder)
        raise

    full = (full or "").strip() or "—"
    await _send_final(message, full, lang, ctx, placeholder, attach_md)


# --- Streaming -----------------------------------------------------------
async def _stream_into(
    placeholder: Message, ctx: AppContext, lang: str, messages, model, api_key
) -> str:
    """Accumulate streamed deltas, live-editing `placeholder` (throttled)."""
    full = ""
    last_edit = 0.0
    throttle = max(ctx.settings.stream_throttle_ms, 0) / 1000.0
    async for delta in ctx.orclient.chat_stream(messages, model=model, api_key=api_key):
        full += delta
        now = time.monotonic()
        if now - last_edit >= throttle and full.strip():
            # Live preview is plain text (head of the answer); the formatted,
            # complete version replaces it once streaming finishes.
            preview = full[:TELEGRAM_MESSAGE_LIMIT]
            try:
                await placeholder.edit_text(preview, parse_mode=None)
            except TelegramBadRequest:
                pass  # "not modified" / transient -> skip this tick
            last_edit = now
    return full


# --- Final rendered delivery --------------------------------------------
async def _send_final(
    message: Message, text: str, lang: str, ctx: AppContext, placeholder: Message, attach_md: bool
) -> None:
    plain = render.plain_chunks(text)
    too_long = len(text) > FILE_THRESHOLD_CHARS or len(plain) > MAX_MESSAGE_CHUNKS

    if too_long:
        # Very long: a single .md file instead of a wall of messages. For Pro/BYO
        # this doubles as their always-on raw answer (so we don't attach twice).
        await _safe_delete(placeholder)
        caption = t("result_md_caption", lang) if attach_md else t("long_result_heads_up", lang)
        await _send_md(message, text, lang, caption)
        return

    await _send_rendered(message, text, lang, ctx, placeholder)
    if attach_md:
        await _send_md(message, text, lang, t("result_md_caption", lang))


async def _send_rendered(
    message: Message, text: str, lang: str, ctx: AppContext, placeholder: Message | None
) -> None:
    """Send the formatted answer: rich -> MarkdownV2 -> plain. Reuses placeholder."""
    global _rich_supported

    # 1) Best-effort native rich message (whole answer, no manual splitting).
    if ctx.settings.rich_messages_enabled and _rich_supported:
        rich = render.build_rich(text)
        if rich is not None:
            try:
                await message.bot.send_rich_message(message.chat.id, rich_message=rich)
            except Exception as exc:  # noqa: BLE001 - unsupported/parse -> drop down
                _rich_supported = False
                logger.info("sendRichMessage unsupported, using MarkdownV2 (%s)", exc)
            else:
                await _safe_delete(placeholder)
                return

    # 2) MarkdownV2 (vetted converter). 3) Plain text on any parse rejection.
    md_chunks = render.markdownv2_chunks(text)
    if await _try_send_chunks(message, md_chunks, ParseMode.MARKDOWN_V2, placeholder):
        return
    await _try_send_chunks(message, render.plain_chunks(text), None, placeholder, force=True)


async def _try_send_chunks(
    message: Message,
    chunks: list[str],
    parse_mode: str | None,
    placeholder: Message | None,
    *,
    force: bool = False,
) -> bool:
    """Send chunks (first via placeholder edit). False if the mode is rejected.

    ``force`` (the final plain fallback) ignores parse errors and always sends.
    """
    for i, chunk in enumerate(chunks):
        try:
            if i == 0 and placeholder is not None:
                await placeholder.edit_text(chunk, parse_mode=parse_mode)
            else:
                await message.answer(chunk, parse_mode=parse_mode)
        except TelegramBadRequest:
            if force:
                # Last resort: drop formatting entirely for this chunk.
                try:
                    if i == 0 and placeholder is not None:
                        await placeholder.edit_text(chunk, parse_mode=None)
                    else:
                        await message.answer(chunk, parse_mode=None)
                except TelegramBadRequest:
                    logger.warning("Dropped a chunk Telegram refused even as plain text")
                continue
            if i == 0:
                return False  # nothing sent yet -> let the caller try a lower mode
            # A later chunk failed: don't lose it — append it as plain text.
            try:
                await message.answer(chunk, parse_mode=None)
            except TelegramBadRequest:
                logger.warning("Dropped a trailing chunk Telegram refused")
    return True


async def _send_md(message: Message, text: str, lang: str, caption: str) -> None:
    document = BufferedInputFile(text.encode("utf-8"), filename=texts.RESULT_FILENAME)
    await message.answer_document(document, caption=caption)


async def _safe_delete(msg: Message | None) -> None:
    if msg is None:
        return
    try:
        await msg.delete()
    except Exception:  # noqa: BLE001
        pass
