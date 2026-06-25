"""Media download + ffmpeg/ffprobe helpers.

All ffmpeg/ffprobe work happens via async subprocesses so the polling loop is
never blocked. Temp files are always cleaned up by the caller (see transcribe.py).
"""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot

logger = logging.getLogger(__name__)

# Telegram Bot API caps file downloads (getFile) at 20 MB.
TELEGRAM_MAX_DOWNLOAD = 20 * 1024 * 1024


class FileTooLarge(Exception):
    """Raised when a Telegram file exceeds the 20 MB getFile limit."""


async def download(bot: Bot, file_id: str) -> bytes:
    """Download a Telegram file by id, enforcing the 20 MB cap.

    Raises FileTooLarge if the file is too big to fetch.
    """
    file = await bot.get_file(file_id)
    if file.file_size and file.file_size > TELEGRAM_MAX_DOWNLOAD:
        raise FileTooLarge(file.file_size)
    buffer = await bot.download_file(file.file_path)
    data = buffer.read()
    if len(data) > TELEGRAM_MAX_DOWNLOAD:
        raise FileTooLarge(len(data))
    return data


async def _run(cmd: list[str]) -> tuple[int, bytes, bytes]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout, stderr


async def probe_duration(path: str) -> float | None:
    """Return media duration in seconds, or None if it can't be determined."""
    rc, out, _ = await _run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", path,
        ]
    )
    if rc != 0:
        return None
    try:
        return float(out.decode().strip())
    except (ValueError, AttributeError):
        return None


async def has_audio_stream(path: str) -> bool:
    """True if the file has at least one audio stream."""
    rc, out, _ = await _run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0", path,
        ]
    )
    return rc == 0 and bool(out.strip())


async def extract_audio_to_mp3(in_path: str, out_path: str) -> bool:
    """Extract the audio track of a video into an mp3 file. False on failure."""
    rc, _, err = await _run(
        ["ffmpeg", "-y", "-i", in_path, "-vn", "-c:a", "libmp3lame", "-b:a", "64k", out_path]
    )
    if rc != 0:
        logger.warning("extract_audio_to_mp3 failed: %s", err.decode(errors="replace")[:300])
    return rc == 0 and os.path.exists(out_path)


async def split_audio_to_mp3(in_path: str, out_dir: str, segment_time: int = 50) -> list[str]:
    """Split audio into ~segment_time-second mp3 chunks. Returns sorted paths.

    Re-encoding (rather than stream-copy) guarantees clean, independently
    decodable segments regardless of the source codec.
    """
    pattern = os.path.join(out_dir, "seg_%03d.mp3")
    rc, _, err = await _run(
        [
            "ffmpeg", "-y", "-i", in_path,
            "-vn", "-c:a", "libmp3lame", "-b:a", "64k",
            "-f", "segment", "-segment_time", str(segment_time),
            "-reset_timestamps", "1", pattern,
        ]
    )
    if rc != 0:
        logger.warning("split_audio_to_mp3 failed: %s", err.decode(errors="replace")[:300])
        return []
    parts = sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.startswith("seg_")
    )
    return parts
