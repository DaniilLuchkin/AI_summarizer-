"""Async OpenRouter client: chat (text), vision, and transcription.

Everything goes through one API key and the OpenAI-compatible endpoints.
See https://openrouter.ai/docs for the exact request shapes.
"""

from __future__ import annotations

import base64
import logging

import httpx

from bot.config import Settings

logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter returns an error or an unexpected payload."""


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # A single shared AsyncClient (connection pooling). Generous timeout
        # because transcription/vision can be slow; we segment audio so that no
        # single request exceeds the upstream ~60s-of-audio limit.
        self._client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                # OpenRouter uses these for attribution / rankings.
                "HTTP-Referer": settings.openrouter_app_referer,
                "X-Title": settings.openrouter_app_title,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(180.0, connect=15.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- Text / chat -----------------------------------------------------
    async def chat(
        self, messages: list[dict], model: str | None = None, api_key: str | None = None
    ) -> str:
        """Plain OpenAI-style chat completion. Returns the assistant text.

        `api_key` overrides the global key for this call (bring-your-own-key).
        """
        payload = {"model": model or self._settings.model_text, "messages": messages}
        data = await self._post("/chat/completions", payload, api_key=api_key)
        return self._extract_message(data)

    # --- Vision ----------------------------------------------------------
    async def vision(
        self, image_bytes: bytes, prompt: str, mime: str = "image/jpeg", api_key: str | None = None
    ) -> str:
        """Send one image + a text prompt to the vision model (base64 data URI)."""
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ]
        payload = {"model": self._settings.model_vision, "messages": messages}
        data = await self._post("/chat/completions", payload, api_key=api_key)
        return self._extract_message(data)

    # --- Transcription ---------------------------------------------------
    async def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: str | None = None,
        api_key: str | None = None,
    ) -> str:
        """Transcribe one audio chunk.

        `input_audio.data` is RAW base64 (not a data URI). The caller is
        responsible for keeping each chunk under the upstream ~60s limit.
        """
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        payload: dict = {
            "model": self._settings.model_transcribe,
            "input_audio": {"data": b64, "format": audio_format},
        }
        if language:
            payload["language"] = language
        data = await self._post("/audio/transcriptions", payload, api_key=api_key)
        text = data.get("text")
        if not isinstance(text, str):
            raise OpenRouterError(f"Unexpected transcription response: {data!r}")
        return text.strip()

    # --- Image generation ------------------------------------------------
    async def generate_image(
        self, prompt: str, aspect_ratio: str = "1:1", api_key: str | None = None
    ) -> bytes:
        """Generate an image and return its raw bytes.

        OpenRouter may return either an http(s) URL or a base64 data URI; we
        handle both. Network downloads follow redirects with a 60s timeout.
        """
        payload = {
            "model": self._settings.model_image,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        data = await self._post("/images", payload, api_key=api_key)
        try:
            url = data["data"][0]["url"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError(f"Unexpected image response: {data!r}") from exc

        if url.startswith("data:"):
            # data:image/...;base64,<payload>
            b64 = url.split(",", 1)[1]
            return base64.b64decode(b64)

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    # --- Key validation --------------------------------------------------
    async def validate_key(self, api_key: str) -> bool:
        """Cheap check that a BYO key is usable (GET /key returns 200 if valid)."""
        try:
            resp = await self._client.get(
                "/key", headers={"Authorization": f"Bearer {api_key}"}
            )
        except httpx.HTTPError:
            return False
        return resp.status_code == 200

    # --- Internals -------------------------------------------------------
    async def _post(self, path: str, payload: dict, api_key: str | None = None) -> dict:
        # A per-call key (BYO) overrides the client's default Authorization header.
        extra = {"Authorization": f"Bearer {api_key}"} if api_key else None
        try:
            resp = await self._client.post(path, json=payload, headers=extra)
        except httpx.HTTPError as exc:  # network / timeout
            raise OpenRouterError(f"HTTP error calling {path}: {exc}") from exc
        if resp.status_code >= 400:
            # Surface the body to logs but keep user-facing messages friendly.
            logger.error("OpenRouter %s -> %s: %s", path, resp.status_code, resp.text[:500])
            raise OpenRouterError(f"OpenRouter {resp.status_code} on {path}")
        # httpx parses the JSON body from raw bytes per the JSON spec (UTF-8),
        # so Cyrillic/Unicode in the model's reply stays intact. Never decode the
        # body manually with a non-UTF-8 codec here.
        return resp.json()

    @staticmethod
    def _extract_message(data: dict) -> str:
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise OpenRouterError(f"Unexpected chat response: {data!r}") from exc
