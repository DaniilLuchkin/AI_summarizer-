"""Build a Unicode (Cyrillic-capable) PDF from simple structured text.

The LLM is asked (see PDF_SYSTEM) to emit lines using:
    '# '  -> main heading
    '## ' -> subheading
    '- '  -> bullet
    ''    -> blank spacing
    else  -> normal paragraph

fpdf2 (2.8+) no longer bundles fonts, so we load DejaVuSans from the system
(installed via `fonts-dejavu-core` in the Dockerfile). Without a Unicode TTF,
Cyrillic would render as mojibake, so this is required.
"""

from __future__ import annotations

import os

from fpdf import FPDF

# Candidate locations for the DejaVu TTFs, in priority order. The Debian
# `fonts-dejavu-core` package installs them under the first path.
_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _first_existing(paths: list[str]) -> str | None:
    return next((p for p in paths if os.path.exists(p)), None)


def build_pdf(text: str) -> bytes:
    """Render structured text into PDF bytes (A4, 20mm margins, DejaVu font)."""
    regular = _first_existing(_REGULAR_CANDIDATES)
    bold = _first_existing(_BOLD_CANDIDATES)
    if not regular:
        raise RuntimeError("DejaVuSans.ttf not found (install fonts-dejavu-core)")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_margins(20, 20, 20)
    pdf.add_font("DejaVu", "", regular)
    # Fall back to the regular face for bold if the bold TTF is missing.
    pdf.add_font("DejaVu", "B", bold or regular)
    pdf.add_page()

    width = pdf.epw  # effective page width (passing 0 errors out in fpdf2 2.8)
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if not line:
            pdf.ln(4)
            continue
        if line.startswith("# "):
            pdf.set_font("DejaVu", "B", 16)
            pdf.multi_cell(width, 9, line[2:].strip())
        elif line.startswith("## "):
            pdf.set_font("DejaVu", "B", 13)
            pdf.multi_cell(width, 8, line[3:].strip())
        elif line.startswith("- "):
            pdf.set_font("DejaVu", "", 11)
            # Indent bullets a little; keep them inside the right margin.
            pdf.set_x(pdf.l_margin + 6)
            pdf.multi_cell(width - 6, 6, f"• {line[2:].strip()}")
        else:
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(width, 6, line)

    # fpdf2 2.8 returns a bytearray; normalize to bytes.
    return bytes(pdf.output())
