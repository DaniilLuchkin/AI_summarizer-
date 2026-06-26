"""Turn raw audio bytes into text, transparently segmenting long audio.

The upstream transcription provider times out at ~60s of audio per request,
so we probe the duration and, when needed, split into ~50s mp3 segments,
transcribe each, and concatenate the results in order.
"""

from __future__ import annotations

import logging
import os
import tempfile

from bot.services import media
from bot.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Stay safely under the ~60s upstream limit.
MAX_SECONDS_PER_REQUEST = 55
SEGMENT_SECONDS = 50


async def transcribe_media(
    orclient: OpenRouterClient,
    raw_bytes: bytes,
    source_format: str,
    is_video: bool,
    language: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """Transcribe audio (or a video's audio track) to text.

    Returns the transcript, or None if the video has no audio track.
    """
    with tempfile.TemporaryDirectory(prefix="tg_audio_") as tmp:
        in_path = os.path.join(tmp, f"input.{source_format}")
        with open(in_path, "wb") as fh:
            fh.write(raw_bytes)

        # For video / video notes we first need to pull out the audio track.
        if is_video:
            if not await media.has_audio_stream(in_path):
                return None
            work_path = os.path.join(tmp, "audio.mp3")
            if not await media.extract_audio_to_mp3(in_path, work_path):
                raise RuntimeError("ffmpeg failed to extract audio")
            work_format = "mp3"
        else:
            work_path = in_path
            work_format = source_format

        duration = await media.probe_duration(work_path)

        # Short enough -> one request with the working file as-is.
        if duration is None or duration <= MAX_SECONDS_PER_REQUEST:
            with open(work_path, "rb") as fh:
                data = fh.read()
            return await orclient.transcribe(data, work_format, language, api_key=api_key)

        # Too long -> split into segments and stitch transcripts together.
        seg_dir = os.path.join(tmp, "segments")
        os.makedirs(seg_dir, exist_ok=True)
        segments = await media.split_audio_to_mp3(work_path, seg_dir, SEGMENT_SECONDS)
        if not segments:
            raise RuntimeError("ffmpeg failed to split audio")

        parts: list[str] = []
        for seg_path in segments:
            with open(seg_path, "rb") as fh:
                seg_bytes = fh.read()
            text = await orclient.transcribe(seg_bytes, "mp3", language, api_key=api_key)
            if text:
                parts.append(text)
        return " ".join(parts).strip()
