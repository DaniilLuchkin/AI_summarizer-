"""Photo -> text (OCR + one-line description) via the vision model."""

from __future__ import annotations

from bot.prompts import VISION_PROMPT
from bot.services.openrouter import OpenRouterClient


async def describe_image(
    orclient: OpenRouterClient,
    image_bytes: bytes,
    mime: str = "image/jpeg",
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """Extract verbatim text from an image and append a short description."""
    return await orclient.vision(image_bytes, VISION_PROMPT, mime, api_key=api_key, model=model)
