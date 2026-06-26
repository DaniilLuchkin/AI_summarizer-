"""Automated visual QA for decks: render → detect defects (vision) → fix in code.

The vision model only DETECTS defects (it can't edit a binary .pptx); fixes are
applied deterministically by re-building flagged slides with `overrides` and
re-rendering. Bounded by passes/slides. ANY tooling failure ships the input deck.

Rendering needs LibreOffice (`soffice`) + poppler (`pdftoppm`) in the image.
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Awaitable, Callable

from bot.prompts import DECK_QA_SYSTEM

logger = logging.getLogger(__name__)

_JSON = re.compile(r"\{.*\}", re.DOTALL)
_RENDER_TIMEOUT = 150
# Map a detected issue type to the deterministic override flag we apply.
_FIX_FLAGS = {
    "overflow": "font_step",
    "overlap": "stricter",
    "narrow_wrap": "widen",
    "low_contrast": "contrast",
    "small_margin": "nudge",
}


def _render_slides(deck_bytes: bytes, max_slides: int) -> list[tuple[int, bytes]]:
    """Render a .pptx to per-slide JPEGs via soffice + pdftoppm. [] on failure."""
    with tempfile.TemporaryDirectory(prefix="deckqa_") as d:
        pptx_path = os.path.join(d, "deck.pptx")
        with open(pptx_path, "wb") as fh:
            fh.write(deck_bytes)
        profile = "-env:UserInstallation=file://" + os.path.join(d, "lo")
        subprocess.run(
            ["soffice", profile, "--headless", "--convert-to", "pdf", "--outdir", d, pptx_path],
            check=True, timeout=_RENDER_TIMEOUT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        pdf_path = os.path.join(d, "deck.pdf")
        if not os.path.exists(pdf_path):
            return []
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "150", pdf_path, os.path.join(d, "slide")],
            check=True, timeout=_RENDER_TIMEOUT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        files = sorted(glob.glob(os.path.join(d, "slide*.jpg")))
        out: list[tuple[int, bytes]] = []
        for i, path in enumerate(files[:max_slides], start=1):
            with open(path, "rb") as fh:
                out.append((i, fh.read()))
        return out


def _parse_issues(raw: str) -> list[dict]:
    match = _JSON.search(raw or "")
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return []
    issues = data.get("issues") if isinstance(data, dict) else None
    return [i for i in (issues or []) if isinstance(i, dict) and i.get("type")]


def _overrides_from(issues: list[dict]) -> dict:
    """Turn a slide's issues into a deterministic override dict for re-layout."""
    ov: dict = {}
    for issue in issues:
        flag = _FIX_FLAGS.get(issue.get("type"))
        if flag == "font_step":
            ov["font_step"] = min(ov.get("font_step", 0) + 1, 3)
        elif flag:
            ov[flag] = True
    return ov


def _merge(base: dict[int, dict], new: dict[int, dict]) -> dict[int, dict]:
    merged = {k: dict(v) for k, v in base.items()}
    for slide_no, ov in new.items():
        cur = merged.setdefault(slide_no, {})
        for k, v in ov.items():
            cur[k] = cur.get(k, 0) + v if k == "font_step" else v
    return merged


async def polish(
    *,
    deck_bytes: bytes,
    rebuild: Callable[[dict[int, dict]], bytes],
    detect_slide: Callable[[int, bytes], Awaitable[str]],
    max_passes: int,
    max_slides: int,
) -> bytes:
    """Render→detect→fix loop. `rebuild(overrides)` returns new deck bytes;
    `detect_slide(n, jpg)` returns the QA model's JSON for one slide image.
    Returns the best deck we have; never raises."""
    passes = max(1, min(int(max_passes), 2))
    overrides: dict[int, dict] = {}
    current = deck_bytes
    to_check: set[int] | None = None  # None == all slides

    for _ in range(passes):
        try:
            images = await asyncio.to_thread(_render_slides, current, max_slides)
        except Exception:  # noqa: BLE001 - soffice/poppler missing or failed
            logger.warning("deck QA: render failed, shipping un-QA'd deck")
            return current
        if not images:
            return current
        if to_check is not None:
            images = [im for im in images if im[0] in to_check]

        new_ov: dict[int, dict] = {}
        for slide_no, jpg in images:
            try:
                reply = await detect_slide(slide_no, jpg)
            except Exception:  # noqa: BLE001 - one slide's QA call failed
                logger.warning("deck QA: detection failed for slide %s", slide_no)
                continue
            ov = _overrides_from(_parse_issues(reply))
            if ov:
                new_ov[slide_no] = ov

        if not new_ov:
            break
        merged = _merge(overrides, new_ov)
        if merged == overrides:
            break
        overrides = merged
        try:
            current = await asyncio.to_thread(rebuild, overrides)
        except Exception:  # noqa: BLE001
            logger.exception("deck QA: rebuild failed, shipping previous deck")
            return current
        to_check = set(new_ov)  # next pass only re-checks the slides we touched

    return current
