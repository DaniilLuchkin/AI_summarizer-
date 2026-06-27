"""Text-splitting helper shared by the rendering/delivery layer.

`services/delivery.py` owns sending results to Telegram now (clean HTML, live
streaming, large-answer file). This module only keeps the boundary-aware
splitter and the message-size constant they build on.
"""

from __future__ import annotations

TELEGRAM_MESSAGE_LIMIT = 4096


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into <= limit chunks, breaking on line boundaries.

    A single line longer than `limit` is hard-split. Blank lines are preserved,
    so paragraph boundaries are respected naturally.
    """
    units: list[str] = []
    for line in text.split("\n"):
        if len(line) <= limit:
            units.append(line)
        else:
            for i in range(0, len(line), limit):
                units.append(line[i:i + limit])

    chunks: list[str] = []
    buf = ""
    for unit in units:
        candidate = unit if not buf else f"{buf}\n{unit}"
        if len(candidate) <= limit:
            buf = candidate
        else:
            chunks.append(buf)
            buf = unit
    if buf:
        chunks.append(buf)
    return chunks
