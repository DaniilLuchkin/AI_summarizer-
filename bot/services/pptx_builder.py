"""Build a .pptx file from the LLM's JSON slide description.

Input shape (produced by PRESENTATION_SYSTEM):
    {"title": "...", "slides": [{"title": "...", "bullets": ["...", ...]}, ...]}

We tolerate the model wrapping the JSON in ```json fences or adding stray text,
so we extract the first {...} block before parsing.
"""

from __future__ import annotations

import io
import json
import re

from pptx import Presentation
from pptx.util import Pt

# Layout indexes in the default python-pptx template.
_TITLE_SLIDE = 0
_TITLE_AND_CONTENT = 1

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_slides(raw: str) -> dict:
    """Parse the model output into a {title, slides} dict (lenient)."""
    match = _JSON_BLOCK.search(raw or "")
    if not match:
        raise ValueError("no JSON object found in model output")
    data = json.loads(match.group(0))
    if not isinstance(data, dict) or "slides" not in data:
        raise ValueError("JSON missing 'slides'")
    return data


def build_pptx(data: dict) -> bytes:
    """Render the slide dict into .pptx bytes using the default theme."""
    prs = Presentation()

    # Title slide.
    title_slide = prs.slides.add_slide(prs.slide_layouts[_TITLE_SLIDE])
    title_slide.shapes.title.text = str(data.get("title") or "Presentation")

    # Content slides.
    for slide in data.get("slides", []):
        layout = prs.slide_layouts[_TITLE_AND_CONTENT]
        s = prs.slides.add_slide(layout)
        s.shapes.title.text = str(slide.get("title") or "")

        bullets = [str(b) for b in slide.get("bullets", []) if str(b).strip()]
        body = s.placeholders[1].text_frame
        body.clear()
        for i, bullet in enumerate(bullets):
            # First paragraph already exists after clear(); add the rest.
            paragraph = body.paragraphs[0] if i == 0 else body.add_paragraph()
            paragraph.text = bullet
            paragraph.font.size = Pt(24)
            paragraph.font.name = "Calibri"

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()
