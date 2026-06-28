"""Parse extra context for custom prompts: files and links -> plain text.

Files: .pdf (pypdf), .docx (python-docx), .txt/.md (read directly).
Links: fetched with httpx, main text extracted with trafilatura (falls back to
a crude HTML-tag strip). Everything is capped to a max number of characters.
"""

from __future__ import annotations

import io
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Matches http(s) URLs in free text.
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
# Very small fallback HTML cleaner.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def extract_urls(text: str) -> list[str]:
    """Return all http(s) URLs found in the given text (order-preserving, unique)."""
    seen: list[str] = []
    for match in _URL_RE.findall(text or ""):
        url = match.rstrip(".,);")
        if url not in seen:
            seen.append(url)
    return seen


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(context truncated)"
    return text


# --- Files ---------------------------------------------------------------
def parse_file(filename: str, data: bytes, max_chars: int) -> str:
    """Parse a supported document into text. Raises ValueError if unsupported."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _truncate(_parse_pdf(data), max_chars)
    if name.endswith(".docx"):
        return _truncate(_parse_docx(data), max_chars)
    if name.endswith(".txt") or name.endswith(".md"):
        return _truncate(data.decode("utf-8", errors="replace"), max_chars)
    raise ValueError(f"unsupported file type: {filename}")


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader  # imported lazily to keep startup fast

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def _parse_docx(data: bytes) -> str:
    import docx  # python-docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


# --- Links ---------------------------------------------------------------
async def fetch_link(url: str, timeout: float, max_chars: int) -> str:
    """Fetch a URL and extract its main readable text."""
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (bot)"}
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # Keep the raw bytes for the extractor (it detects the encoding itself,
        # which correctly handles UTF-8 *and* declared charsets like cp1251).
        # `resp.text` is httpx's charset-aware decode, used only as a fallback.
        raw_bytes = resp.content
        fallback_text = resp.text

    text = _extract_main_text(raw_bytes, fallback_text)
    return _truncate(text, max_chars)


def _extract_main_text(raw_bytes: bytes, fallback_text: str) -> str:
    """Prefer trafilatura's main-content extraction; fall back to tag stripping.

    trafilatura is given the raw bytes so it can detect the page's real encoding
    instead of us guessing — this avoids latin-1/UTF-8 double-encoding mojibake.
    """
    try:
        import trafilatura

        extracted = trafilatura.extract(
            raw_bytes, include_comments=False, include_tables=False
        )
        if extracted:
            return extracted
    except Exception as exc:  # noqa: BLE001 - never let extraction crash the bot
        logger.warning("trafilatura failed, falling back to tag strip: %s", exc)

    # Crude fallback: drop tags and collapse whitespace (uses httpx's decoded text).
    stripped = _TAG_RE.sub(" ", fallback_text)
    stripped = _WS_RE.sub("\n\n", stripped)
    return " ".join(stripped.split())
