"""Batch collection: debounce incoming messages, then finalize into one document.

Entry rules (default FSM state):
  * plain typed text while a batch is active -> run as a custom prompt (Change 2),
  * otherwise append to the current batch (starting a new one if the previous
    batch was already finalized) and (re)arm the debounce timer.

`handle_incoming` / `is_new_batch_trigger` are also reused by actions.py when a
forwarded message arrives while an action is staged.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginHiddenUser,
    MessageOriginUser,
)

from bot import texts
from bot.handlers import execute
from bot.handlers.run import build_actions_keyboard, build_upgrade_keyboard
from bot.runtime import AppContext
from bot.services import media, transcribe, vision
from bot.services.batch import ChatState
from bot.services.context import parse_file
from bot.services.media import FileTooLarge
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)


def build_router(ctx: AppContext) -> Router:
    router = Router(name="collect")

    # Only handle private-chat messages in the default state; staged-action /
    # custom states are handled by actions.py, and group chats by group.py.
    @router.message(StateFilter(None), F.chat.type == "private")
    async def collect(message: Message, state: FSMContext, bot: Bot) -> None:
        await handle_incoming(ctx, message, state, bot)

    return router


def is_new_batch_trigger(message: Message) -> bool:
    """A forwarded message or directly-sent media starts a new batch.

    Plain typed text and a directly-attached document are NOT triggers (they are
    a custom prompt / context respectively).
    """
    if message.forward_origin is not None:
        return True
    return bool(
        message.voice or message.audio or message.video or message.video_note or message.photo
    )


def _is_plain_text(message: Message) -> bool:
    """Directly-sent (non-forwarded) text message."""
    return bool(message.text) and message.forward_origin is None


async def handle_incoming(ctx: AppContext, message: Message, state: FSMContext, bot: Bot) -> None:
    """Route an incoming default-state message to custom-prompt or collection."""
    chat_state = ctx.store.get_or_create(message.chat.id)

    # Typed text against an already-finalized batch -> custom prompt (no tap).
    if chat_state.has_active_batch and _is_plain_text(message):
        await execute.run_typed_custom(ctx, message, bot, ctx.store.lang_for(message))
        return

    # A fresh message after a finalized batch starts a new batch.
    if chat_state.has_active_batch:
        ctx.store.start_new_batch(chat_state)
        await state.clear()

    # Refresh the auto-detected language at the start of each new batch
    # (a manual /lang override still wins via get_lang/lang_for).
    if not chat_state.pending:
        ctx.store.set_lang(message.chat.id, resolve_lang(message.from_user.language_code))

    lang = ctx.store.lang_for(message)
    added = ctx.store.add_pending(chat_state, message)
    if not added and not chat_state.limit_notified:
        chat_state.limit_notified = True
        await message.answer(
            t("batch_limit_reached", lang).format(limit=ctx.settings.max_batch_messages)
        )

    _reschedule_finalize(ctx, chat_state, bot)


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
            lang = ctx.store.get_lang(chat_state.chat_id) or "en"
            await bot.send_message(chat_state.chat_id, t("generic_error", lang))
        except Exception:  # noqa: BLE001
            pass


async def _finalize(ctx: AppContext, chat_state: ChatState, bot: Bot) -> None:
    """Process every pending message into a labeled line and show the keyboard."""
    pending = chat_state.pending
    chat_state.pending = []
    if not pending:
        return

    lang = ctx.store.get_lang(chat_state.chat_id) or "en"
    user_id = pending[0].from_user.id if pending[0].from_user else 0

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

    # BYO-key users transcribe/OCR on their own key and bypass quotas.
    api_key = await ctx.quota.api_key_for(user_id)

    item_texts: list[str] = []
    notes: list[str] = []
    limited = False  # True if any item was skipped because a quota was reached
    index = 0
    for msg in pending:
        index += 1
        kind = _kind(msg)
        name = _sender_name(msg, lang)
        try:
            text, note, item_limited = await _process_message(
                ctx, bot, msg, index, name, user_id, api_key
            )
        except FileTooLarge:
            notes.append(t("skipped_too_large", lang).format(index=index, kind=kind))
            continue
        except Exception as exc:  # noqa: BLE001 - keep processing the rest
            logger.exception("Failed to process item %s", index)
            notes.append(t("skipped_error", lang).format(index=index, kind=kind, error=exc))
            continue
        limited = limited or item_limited
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

    # If any item was skipped due to a daily/quota limit, nudge toward Pro
    # with a one-tap upgrade button on the hint message.
    if limited:
        await bot.send_message(
            chat_state.chat_id, t("upgrade_hint", lang), reply_markup=build_upgrade_keyboard(lang)
        )

    await bot.send_message(
        chat_state.chat_id, t("batch_ready", lang), reply_markup=build_actions_keyboard(lang)
    )


# --- Sender name + kind --------------------------------------------------
def _sender_name(message: Message, lang: str) -> str:
    """Display name of who sent the (possibly forwarded) message."""
    origin = message.forward_origin
    if origin is None:
        return t("label_you", lang)  # directly sent by the interlocutor
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
    ctx: AppContext, bot: Bot, msg: Message, index: int, name: str, user_id: int, api_key: str | None
) -> tuple[str | None, str | None, bool]:
    """Convert one message into a labeled context line.

    Returns (item_text, optional_note, limited?) where `limited` is True when the
    item was skipped because the user hit a daily/quota limit.
    """
    caption = (msg.caption or "").strip()
    lang = ctx.store.get_lang(msg.chat.id) or "en"

    if msg.text:
        return _label(index, name, texts.KIND_TEXT, msg.text.strip()), None, False

    # --- Audio-bearing items: probe duration -> consume_audio -> cache/transcribe
    if msg.voice or msg.audio or msg.video_note or msg.video:
        return await _process_audio(ctx, bot, msg, index, name, caption, lang, user_id, api_key)

    if msg.photo:
        largest = msg.photo[-1]
        ok, _ = await ctx.quota.consume_photo(user_id, 1)
        if not ok:
            return _label(index, name, texts.KIND_PHOTO, t("item_not_ocr", lang)), None, True
        text = await _cached_or_call(
            ctx, largest.file_unique_id, "vision",
            lambda data: vision.describe_image(ctx.orclient, data, api_key=api_key),
            lambda: media.download(bot, largest.file_id),
        )
        return _label(index, name, texts.KIND_PHOTO, _join(text, caption)), None, False

    if msg.document:
        data = await media.download(bot, msg.document.file_id)
        try:
            parsed = parse_file(msg.document.file_name or "", data, ctx.settings.context_max_chars)
        except ValueError:
            return None, t("unsupported_document", lang).format(index=index), False
        return _label(index, name, texts.KIND_DOCUMENT, _join(parsed, caption)), None, False

    return None, None, False


async def _process_audio(ctx, bot, msg, index, name, caption, lang, user_id, api_key):
    """Handle voice/audio/video/video_note: quota by duration, cache, transcribe."""
    if msg.voice:
        file_id, fuid, fmt, kind, is_video = msg.voice.file_id, msg.voice.file_unique_id, "ogg", texts.KIND_VOICE, False
    elif msg.audio:
        fmt = _audio_format(msg.audio.mime_type, msg.audio.file_name)
        file_id, fuid, kind, is_video = msg.audio.file_id, msg.audio.file_unique_id, texts.KIND_AUDIO, False
    elif msg.video_note:
        file_id, fuid, fmt, kind, is_video = msg.video_note.file_id, msg.video_note.file_unique_id, "mp4", texts.KIND_VIDEO_NOTE, True
    else:  # msg.video
        file_id, fuid, fmt, kind, is_video = msg.video.file_id, msg.video.file_unique_id, "mp4", texts.KIND_VIDEO, True

    data = await media.download(bot, file_id)  # raises FileTooLarge if >20MB
    duration = await media.probe_duration_bytes(data, fmt) or 0

    ok, _ = await ctx.quota.consume_audio(user_id, int(duration))
    if not ok:
        return _label(index, name, kind, t("item_not_transcribed", lang)), None, True

    # Cache hit avoids re-billing OpenRouter for the same file.
    cached = await ctx.db.media_cache_get(fuid)
    if cached is not None:
        return _label(index, name, kind, _join(cached, caption)), None, False

    transcript = await transcribe.transcribe_media(
        ctx.orclient, data, fmt, is_video=is_video, api_key=api_key
    )
    if transcript is None:  # video with no audio track
        note = t("skipped_no_audio", lang).format(index=index)
        if caption:
            return _label(index, name, kind, caption), note, False
        return None, note, False
    await ctx.db.media_cache_put(fuid, "transcript", transcript)
    return _label(index, name, kind, _join(transcript, caption)), None, False


async def _cached_or_call(ctx, file_unique_id, kind, call_with_data, download):
    """Return cached derived text, else download + call the model + cache it."""
    cached = await ctx.db.media_cache_get(file_unique_id)
    if cached is not None:
        return cached
    data = await download()
    text = await call_with_data(data)
    await ctx.db.media_cache_put(file_unique_id, kind, text)
    return text


def _label(index: int, name: str, kind: str, body: str) -> str:
    return f"[{index}] {name} ({kind}): {body}".strip()


def _join(primary: str | None, caption: str) -> str:
    parts = [p for p in [(primary or "").strip(), caption] if p]
    return "\n".join(parts) if parts else "—"


def _audio_format(mime: str | None, filename: str | None) -> str:
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
