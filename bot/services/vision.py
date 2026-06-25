"""Photo -> text (OCR + one-line description) via the vision model."""

from __future__ import annotations

from bot.prompts import VISION_PROMPT
from bot.services.openrouter import OpenRouterClient


async def describe_image(
    orclient: OpenRouterClient, image_bytes: bytes, mime: str = "image/jpeg"
) -> str:
    """Extract verbatim text from an image and append a short description."""
    return await orclient.vision(image_bytes, VISION_PROMPT, mime)
