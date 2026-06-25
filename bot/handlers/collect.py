"""Batch collection: debounce incoming messages, then finalize into one document.

Each finalized item is labeled with the sender's display name and a technical
"kind" tag, e.g. `[1] Иван Петров (voice → transcript): …`. The per-chat UI
language is set when a new batch starts and used for all status messages.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginHiddenUser,
    MessageOriginUser,
)

from bot import texts
from bot.handlers.run import build_actions_keyboard
from bot.runtime import AppContext
from bot.services import media, transcribe, vision
from bot.services.batch import ChatState
from bot.services.context import parse_file
from bot.services.media import FileTooLarge
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)


def build_router(ctx: AppContext) -> Router:
    router = Router(name="collect")

    @router.message()
    async def collect(message: Message, state: FSMContext, bot: Bot) -> None:
        """Catch-all for default-state messages -> batch collection."""
        chat_state = ctx.store.get_or_create(message.chat.id)

        # A fresh message after a finalized batch starts a new batch.
        if chat_state.has_active_batch:
            ctx.store.start_new_batch(chat_state)
            await state.clear()

        # Set/refresh the UI language at the start of each new batch.
        if not chat_state.pending:
            chat_state.lang = resolve_lang(message.from_user.language_code)

        added = ctx.store.add_pending(chat_state, message)
        if not added and not chat_state.limit_notified:
            chat_state.limit_notified = True
            await message.answer(
                t("batch_limit_reached", chat_state.lang).format(
                    limit=ctx.settings.max_batch_messages
                )
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
            await bot.send_message(chat_state.chat_id, t("generic_error", chat_state.lang))
        except Exception:  # noqa: BLE001
            pass


async def _finalize(ctx: AppContext, chat_state: ChatState, bot: Bot) -> None:
    """Process every pending message into a labeled line and show the keyboard."""
    pending = chat_state.pending
    chat_state.pending = []
    if not pending:
        return

    lang = chat_state.lang
    user_id = pending[0].from_user.id if pending[0].from_user else 0

    # Batch-level rate limit (counts one finalized batch).
    allowed, reset_in = ctx.limiter.check_batch(user_id)
    if not allowed:
        minutes = max(1, round(reset_in / 60))
        await bot.send_message(
            chat_state.chat_id,
            t("rate_limit_batches", lang).format(
                limit=ctx.settings.max_batches_per_hour, minutes=minutes
            ),
        )
        return
    ctx.limiter.record_batch(user_id)

    status = await bot.send_message(chat_state.chat_id, t("finalizing", lang))

    item_texts: list[str] = []
    notes: list[str] = []
    index = 0
    for msg in pending:
        index += 1
        kind = _kind(msg)
        name = _sender_name(msg, lang)
        try:
            text, note = await _process_message(ctx, bot, msg, index, name)
        except FileTooLarge:
            notes.append(t("skipped_too_large", lang).format(index=index, kind=kind))
            continue
        except Exception as exc:  # noqa: BLE001 - keep processing the rest
            logger.exception("Failed to process item %s", index)
            notes.append(t("skipped_error", lang).format(index=index, kind=kind, error=exc))
            continue
        if text is not None:
            item_texts.append(text)
        if note:
            notes.append(note)

    chat_state.item_texts = item_texts

    await _safe_delete(status)
    for note in notes:
        await bot.send_message(chat_state.chat_id, note)

    if not item_texts:
        await bot.send_message(chat_state.chat_id, t("empty_batch", lang))
        return

    await bot.send_message(
        chat_state.chat_id, t("batch_ready", lang), reply_markup=build_actions_keyboard(lang)
    )


# --- Sender name + kind --------------------------------------------------
def _sender_name(message: Message, lang: str) -> str:
    """Display name of who sent the (possibly forwarded) message."""
    origin = message.forward_origin
    if origin is None:
        # Directly sent by the bot's interlocutor -> localized "You".
        return t("label_you", lang)
    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.full_name
    if isinstance(origin, MessageOriginHiddenUser):
        return origin.sender_user_name
    if isinstance(origin, MessageOriginChannel):
        return origin.chat.title or "Channel"
    if isinstance(origin, MessageOriginChat):
        return origin.sender_chat.title or "Chat"
    return t("label_you", lang)


def _kind(msg: Message) -> str:
    """Technical (English) label for a message's primary content type."""
    if msg.voice:
        return texts.KIND_VOICE
    if msg.video_note:
        return texts.KIND_VIDEO_NOTE
    if msg.video:
        return texts.KIND_VIDEO
    if msg.audio:
        return texts.KIND_AUDIO
    if msg.photo:
        return texts.KIND_PHOTO
    if msg.document:
        return texts.KIND_DOCUMENT
    return texts.KIND_TEXT


async def _process_message(
    ctx: AppContext, bot: Bot, msg: Message, index: int, name: str
) -> tuple[str | None, str | None]:
    """Convert one message into a labeled context line.

    Returns (item_text, optional_note). item_text is None if nothing usable.
    """
    caption = (msg.caption or "").strip()
    lang = ctx.store.get_or_create(msg.chat.id).lang

    if msg.text:
        return _label(index, name, texts.KIND_TEXT, msg.text.strip()), None

    if msg.voice:
        data = await media.download(bot, msg.voice.file_id)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, "ogg", is_video=False)
        return _label(index, name, texts.KIND_VOICE, _join(transcript, caption)), None

    if msg.audio:
        data = await media.download(bot, msg.audio.file_id)
        fmt = _audio_format(msg.audio.mime_type, msg.audio.file_name)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, fmt, is_video=False)
        return _label(index, name, texts.KIND_AUDIO, _join(transcript, caption)), None

    if msg.video_note:
        data = await media.download(bot, msg.video_note.file_id)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, "mp4", is_video=True)
        if transcript is None:
            return None, t("skipped_no_audio", lang).format(index=index)
        return _label(index, name, texts.KIND_VIDEO_NOTE, _join(transcript, caption)), None

    if msg.video:
        data = await media.download(bot, msg.video.file_id)
        transcript = await transcribe.transcribe_media(ctx.orclient, data, "mp4", is_video=True)
        if transcript is None:
            note = t("skipped_no_audio", lang).format(index=index)
            if caption:
                return _label(index, name, texts.KIND_VIDEO, caption), note
            return None, note
        return _label(index, name, texts.KIND_VIDEO, _join(transcript, caption)), None

    if msg.photo:
        largest = msg.photo[-1]  # last size is the biggest
        data = await media.download(bot, largest.file_id)
        extracted = await vision.describe_image(ctx.orclient, data)
        return _label(index, name, texts.KIND_PHOTO, _join(extracted, caption)), None

    if msg.document:
        data = await media.download(bot, msg.document.file_id)
        try:
            parsed = parse_file(msg.document.file_name or "", data, ctx.settings.context_max_chars)
        except ValueError:
            return None, t("unsupported_document", lang).format(index=index)
        return _label(index, name, texts.KIND_DOCUMENT, _join(parsed, caption)), None

    return None, None


def _label(index: int, name: str, kind: str, body: str) -> str:
    return f"[{index}] {name} ({kind}): {body}".strip()


def _join(primary: str | None, caption: str) -> str:
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


async def _safe_delete(msg) -> None:
    try:
        await msg.delete()
    except Exception:  # noqa: BLE001
        pass
