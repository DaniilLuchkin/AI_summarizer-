"""In-memory batch store + combined-document assembly.

State is intentionally non-persistent: a `ChatState` per chat holds the
messages currently being collected (debounced), the finalized item texts, and
the debounce task handle. Everything is lost on restart — that's acceptable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from aiogram.types import Message

from bot.texts import resolve_lang


@dataclass
class ChatState:
    chat_id: int
    # Auto-detected UI language (from language_code), refreshed when a new batch
    # starts. May be None until first set.
    lang: str | None = None
    # Manual /lang choice. When set it wins over `lang` and over language_code.
    lang_override: str | None = None
    # Raw aiogram messages awaiting finalize (the current, not-yet-processed batch).
    pending: list[Message] = field(default_factory=list)
    # Handle to the debounce timer task so we can cancel/reschedule it.
    debounce_task: asyncio.Task | None = None
    # Finalized, labeled item texts that make up the active context document.
    item_texts: list[str] = field(default_factory=list)
    # How many messages were dropped for exceeding MAX_BATCH_MESSAGES.
    dropped: int = 0
    # True once we've notified the user that the batch limit was hit.
    limit_notified: bool = False
    # Last custom-prompt instruction (for the 💾 Save prompt button).
    last_custom_prompt: str | None = None
    # True when the current collecting batch replaced a previously finalized one
    # (drives the one-time "🔄 new batch started" notice at finalize).
    replaced_previous: bool = False
    # Forwarded photos kept for reuse on slides: [{id, bytes, mime, desc}].
    # Image bytes are in-memory only; capped (see BatchStore.retain_photo).
    photos: list[dict] = field(default_factory=list)

    @property
    def has_active_batch(self) -> bool:
        return bool(self.item_texts)


class BatchStore:
    """Keyed by chat id. Pure in-memory, no persistence."""

    def __init__(self, max_batch_messages: int, max_context_chars: int) -> None:
        self._states: dict[int, ChatState] = {}
        self._max_messages = max_batch_messages
        self._max_chars = max_context_chars

    def get(self, chat_id: int) -> ChatState | None:
        return self._states.get(chat_id)

    def get_or_create(self, chat_id: int) -> ChatState:
        state = self._states.get(chat_id)
        if state is None:
            state = ChatState(chat_id=chat_id)
            self._states[chat_id] = state
        return state

    # Cap combined retained image bytes per chat to bound memory.
    PHOTO_RETAIN_MAX_BYTES = 15 * 1024 * 1024

    def retain_photo(self, state: ChatState, data: bytes, mime: str, desc: str) -> int | None:
        """Keep a photo's bytes for slide reuse. Returns its 1-based id, or None
        if adding it would exceed the per-chat memory cap (then it's not kept)."""
        used = sum(len(p["bytes"]) for p in state.photos)
        if used + len(data) > self.PHOTO_RETAIN_MAX_BYTES:
            return None
        photo_id = len(state.photos) + 1
        state.photos.append({"id": photo_id, "bytes": data, "mime": mime, "desc": desc})
        return photo_id

    def add_pending(self, state: ChatState, message: Message) -> bool:
        """Append a message to the pending batch.

        Returns False (and increments `dropped`) if the batch is already full.
        """
        if len(state.pending) >= self._max_messages:
            state.dropped += 1
            return False
        state.pending.append(message)
        return True

    # --- Language ---------------------------------------------------------
    def set_lang(self, chat_id: int, lang: str) -> None:
        """Store the auto-detected language (does not touch a manual override)."""
        self.get_or_create(chat_id).lang = lang

    def set_lang_override(self, chat_id: int, lang: str) -> None:
        """Store a manual /lang choice (wins over detection)."""
        self.get_or_create(chat_id).lang_override = lang

    def get_lang(self, chat_id: int) -> str | None:
        """Override if present, else the stored detected value (may be None)."""
        state = self._states.get(chat_id)
        if state is None:
            return None
        return state.lang_override or state.lang

    def lang_for(self, message: Message) -> str:
        """Effective UI language: override > language_code (ru/uk/en) > en."""
        return self.get_lang(message.chat.id) or resolve_lang(
            message.from_user.language_code if message.from_user else None
        )

    # --- Session lifecycle ------------------------------------------------
    def clear_session(self, chat_id: int) -> None:
        """Drop the batch buffer + cancel the debounce timer. Keeps language."""
        state = self._states.get(chat_id)
        if state is None:
            return
        if state.debounce_task and not state.debounce_task.done():
            state.debounce_task.cancel()
        state.pending = []
        state.item_texts = []
        state.photos = []
        state.dropped = 0
        state.limit_notified = False
        state.last_custom_prompt = None
        state.replaced_previous = False
        state.debounce_task = None

    def start_new_batch(self, state: ChatState) -> None:
        """Replace a finalized batch: cancel any pending timer and drop the old
        context + retained photos so a fresh batch can be collected cleanly."""
        if state.debounce_task and not state.debounce_task.done():
            state.debounce_task.cancel()
        state.item_texts = []
        state.pending = []
        state.photos = []
        state.dropped = 0
        state.limit_notified = False
        state.last_custom_prompt = None
        state.replaced_previous = False

    def assemble_for_llm(self, state: ChatState, max_chars: int | None = None) -> tuple[str, bool]:
        """Join finalized items into one document, truncating oldest if too long.

        Returns (document, truncated?). Oldest items are dropped first so the
        most recent context is preserved. `max_chars` overrides the default cap
        (Pro users get a larger window).
        """
        cap = max_chars or self._max_chars
        items = list(state.item_texts)
        truncated = False
        while items and sum(len(t) + 2 for t in items) > cap:
            items.pop(0)
            truncated = True
        return "\n\n".join(items), truncated
