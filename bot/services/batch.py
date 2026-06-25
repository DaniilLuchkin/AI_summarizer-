"""In-memory batch store + combined-document assembly.

State is intentionally non-persistent: a `ChatState` per chat holds the
messages currently being collected (debounced), the finalized item texts, and
the debounce task handle. Everything is lost on restart — that's acceptable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from aiogram.types import Message


@dataclass
class ChatState:
    chat_id: int
    # Per-user UI language (ru/en/uk), set from the first message of a session
    # and refreshed when a new batch starts.
    lang: str = "ru"
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

    def add_pending(self, state: ChatState, message: Message) -> bool:
        """Append a message to the pending batch.

        Returns False (and increments `dropped`) if the batch is already full.
        """
        if len(state.pending) >= self._max_messages:
            state.dropped += 1
            return False
        state.pending.append(message)
        return True

    def reset(self, chat_id: int) -> None:
        """Clear everything for a chat and cancel any pending debounce timer."""
        state = self._states.get(chat_id)
        if state and state.debounce_task and not state.debounce_task.done():
            state.debounce_task.cancel()
        self._states.pop(chat_id, None)

    def start_new_batch(self, state: ChatState) -> None:
        """Clear finalized context + pending so a fresh batch can be collected."""
        state.item_texts = []
        state.pending = []
        state.dropped = 0
        state.limit_notified = False

    def assemble_for_llm(self, state: ChatState) -> tuple[str, bool]:
        """Join finalized items into one document, truncating oldest if too long.

        Returns (document, truncated?). Oldest items are dropped first so the
        most recent context is preserved.
        """
        items = list(state.item_texts)
        truncated = False
        while items and sum(len(t) + 2 for t in items) > self._max_chars:
            items.pop(0)
            truncated = True
        return "\n\n".join(items), truncated
