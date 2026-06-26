"""In-memory rolling buffer of recent group messages — ephemeral by design.

No Postgres: group content never touches durable storage (privacy + simplicity).
Resetting on redeploy is acceptable and desirable. Per chat we keep at most
`max_messages`, pruning anything older than `ttl_hours` on every add.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class BufferItem:
    message_id: int
    user_name: str
    text: str
    ts: float


class GroupBuffer:
    def __init__(self, max_messages: int, ttl_hours: int) -> None:
        self._buf: dict[int, list[BufferItem]] = defaultdict(list)
        self._max = max_messages
        self._ttl = ttl_hours * 3600

    def add_message(
        self, chat_id: int, message_id: int, user_name: str, text: str, ts: float
    ) -> None:
        self._buf[chat_id].append(BufferItem(message_id, user_name, text, ts))
        self.prune(chat_id)

    def prune(self, chat_id: int) -> None:
        """Drop expired messages and enforce the per-chat size cap."""
        items = self._buf.get(chat_id)
        if not items:
            return
        cutoff = time.time() - self._ttl
        items = [i for i in items if i.ts >= cutoff]
        if len(items) > self._max:
            items = items[-self._max:]
        self._buf[chat_id] = items

    def get_recent(self, chat_id: int, n: int) -> list[BufferItem]:
        """Last `n` items, oldest-first."""
        self.prune(chat_id)
        return list(self._buf.get(chat_id, []))[-n:]

    def get_since(self, chat_id: int, message_id: int) -> list[BufferItem]:
        """Items from `message_id` to now (empty if it's no longer buffered)."""
        self.prune(chat_id)
        items = self._buf.get(chat_id, [])
        for idx, item in enumerate(items):
            if item.message_id == message_id:
                return items[idx:]
        return []

    def clear(self, chat_id: int) -> None:
        self._buf.pop(chat_id, None)
