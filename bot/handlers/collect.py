"""Batch collection: debounce incoming messages, then finalize into one document.

Flow:
  * Every message (in the default FSM state) is appended to the chat's pending
    batch and the debounce timer is reset.
  * When the timer fires, we download media, transcribe/OCR everything, assemble
    the labeled combined document, and show the actions keyboard.

A finalized batch stays "active" so the user can run several actions against it.
Sending fresh messages (outside the custom-prompt FSM) starts a brand-new batch.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import texts
from bot.handlers.run import build_actions_keyboard
from bot.runtime import AppContext
from bot.services import media, transcribe, vision
from bot.services.batch import ChatState
from bot.services.context import parse_file
from bot.services.media import FileTooLarge

logger = logging.getLogger(__name__)


def build_router(ctx: AppContext) -> Router:
    router = Router(name="collect")

    @router.message()
    async def collect(message: Message, state: FSMContext, bot: Bot) -> None:
        """Catch-all handler for messages in the default state -> batch collection."""
        chat_state = ctx.store.get_or_create(message.chat.id)

        # A new incoming message after a batch was finalized means: start over.
        if chat_state.has_active_batch:
            ctx.store.start_new_batch(chat_state)
            await state.clear()

        added = ctx.store.add_pending(chat_state, message)
        if not added and not chat_state.limit_notified:
            chat_state.limit_notified = True
            await message.answer(
                texts.BATCH_LIMIT_REACHED.format(limit=ctx.settings.max_batch_messages)
            )

        _reschedule_finalize(ctx, chat_state, bot)

    return router


def _reschedule_finalize(ctx: AppContext, chat_state: ChatState, bot: Bot) -> None:
    """(Re)start the debounce timer; finalize fires once the user goes quiet."""
    if chat_state.debounce_task and not chat_state.debounce_task.done():
        chat_state.debounce_task.cancel()
    chat_state.debounce_task = asyncio.create_task(_debounce(ctx, chat_state, bot))


async def _debounce(ctx: AppContext, chat_state: ChatState, bot: Bot) -> None:
    try:
        await asyncio.sleep(ctx.settings.debounce_seconds)
    except asyncio.CancelledError:
        return  # a newer message arrived; this timer is stale
    try:
        await _finalize(ctx, chat_state, bot)
    except Exception:  # noqa: BLE001 - background task must never propagate
        logger.exception("Finalize failed for chat %s", chat_state.chat_id)
        try:
            await bot.send_message(chat_state.chat_id, texts.GENERIC_ERROR)
        except Exception:  # noqa: BLE001
            pass


async def _finalize(ctx: AppContext, chat_state: ChatState, bot: Bot) -> None:
    """Process every pending message into labeled text and show the keyboard."""
    pending = chat_state.pending
    chat_state.pending = []
    if not pending:
        return

    user_id = pending[0].from_user.id if pending[0].from_user else 0

    # Batch-level rate limit (counts one finalized batch).
    allowed, reset_in = ctx.limiter.check_batch(user_id)
    if not allowed:
        minutes = max(1, round(reset_in / 60))
        await bot.send_message(
            chat_state.chat_id,
            texts.RATE_LIMIT_BATCHES.format(
                limit=ctx.settings.max_batches_per_hour, minutes=minutes
            ),
        )
        return
    ctx.limiter.record_batch(user_id)

    status = await bot.send_message(chat_state.chat_id, texts.FINALIZING)

    item_texts: list[str] = []
    notes: list[str] = []  # warnings about skipped / failed items
    index = 0
    for msg in pending:
        index += 1
        try:
            text, note = await _process_message(ctx, bot, msg, index)
        except FileTooLarge:
            notes.append(texts.SKIPPED_TOO_LARGE.format(index=index, kind=_kind(msg)))
            continue
        except Exception as exc:  # noqa: BLE001 - keep processing the rest
            logger.exception("Failed to process item %s", index)
            notes.append(texts.SKIPPED_ERROR.format(index=index, kind=_kind(msg), error=exc))
            continue
        if text is not None:
            item_texts.append(text)
        if note:
            notes.append(note)

    chat_state.item_texts = item_texts

    try:
        await status.delete()
    except Exception:  # noqa: BLE001
        pass

    for note in notes:
        await bot.send_message(chat_state.chat_id, note)

    if not item_texts:
        await bot.send_message(chat_state.chat_id, texts.EMPTY_BATCH)
        return

    await bot.send_message(
        chat_state.chat_id, texts.BATCH_READY, reply_markup=build_actions_keyboard()
    )


def _kind(msg: Message) -> str:
    """Human-readable Russian label for a message's primary content type."""
    if msg.voice:
        return texts.LABEL_VOICE
    if msg.video_note:
        return texts.LABEL_VIDEO_NOTE
    if msg.video:
        return texts.LABEL_VIDEO
    if msg.audio:
        return texts.LABEL_AUDIO
    if msg.photo:
        return texts.LABEL_PHOTO
    if msg.document:
        return texts.LABEL_DOCUMENT
    return texts.LABEL_TEXT


async def _process_message(
    ctx: AppContext, bot: Bot, msg: Message, index: int
) -> tuple[str | None, str | None]:
    """Convert one message into a labeled context line.

    Returns (item_text, optional_note). item_text is None if nothing usable.
    """
    caption = (msg.caption or "").strip()

    # --- Plain text ------------------------------------------------------
    if msg.text:
        return _label(index, texts.LABEL_TEXT, msg.text.strip()), None

    # --- Voice -----------------------------------------------------------
    if msg.voice:
        data = await media.download(bot, msg.voice.file_id)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, "ogg", is_video=False)
        return _label(index, texts.LABEL_VOICE, _join(transcript, caption)), None

    # --- Audio -----------------------------------------------------------
    if msg.audio:
        data = await media.download(bot, msg.audio.file_id)
        fmt = _audio_format(msg.audio.mime_type, msg.audio.file_name)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, fmt, is_video=False)
        return _label(index, texts.LABEL_AUDIO, _join(transcript, caption)), None

    # --- Video note ("кружочек") ----------------------------------------
    if msg.video_note:
        data = await media.download(bot, msg.video_note.file_id)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, "mp4", is_video=True)
        if transcript is None:
            return None, texts.SKIPPED_NO_AUDIO.format(index=index)
        return _label(index, texts.LABEL_VIDEO_NOTE, _join(transcript, caption)), None

    # --- Video -----------------------------------------------------------
    if msg.video:
        data = await media.download(bot, msg.video.file_id)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, "mp4", is_video=True)
        if transcript is None:
            note = texts.SKIPPED_NO_AUDIO.format(index=index)
            # Still keep the caption as context if present.
            if caption:
                return _label(index, texts.LABEL_VIDEO, caption), note
            return None, note
        return _label(index, texts.LABEL_VIDEO, _join(transcript, caption)), None

    # --- Photo -----------------------------------------------------------
    if msg.photo:
        largest = msg.photo[-1]  # last size is the biggest
        data = await media.download(bot, largest.file_id)
        extracted = await vision.describe_image(ctx.orclient, data)
        return _label(index, texts.LABEL_PHOTO, _join(extracted, caption)), None

    # --- Document --------------------------------------------------------
    if msg.document:
        data = await media.download(bot, msg.document.file_id)
        try:
            parsed = parse_file(msg.document.file_name or "", data, ctx.settings.context_max_chars)
        except ValueError:
            return None, texts.UNSUPPORTED_DOCUMENT.format(index=index)
        return _label(index, texts.LABEL_DOCUMENT, _join(parsed, caption)), None

    return None, None


def _label(index: int, kind: str, body: str) -> str:
    return f"[{index}] ({kind}): {body}".strip()


def _join(primary: str | None, caption: str) -> str:
    """Combine a transcript/extraction with an optional caption."""
    parts = [p for p in [(primary or "").strip(), caption] if p]
    return "\n".join(parts) if parts else "—"


def _audio_format(mime: str | None, filename: str | None) -> str:
    """Best-effort container format for the transcription request."""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"mp3", "m4a", "wav", "ogg", "flac", "webm", "mp4"}:
            return ext
    mapping = {
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/ogg": "ogg",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/flac": "flac",
        "audio/webm": "webm",
    }
    return mapping.get((mime or "").lower(), "mp3")
