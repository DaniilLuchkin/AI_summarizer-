"""System prompts for predefined actions + special generators.

Button labels are NOT here — they live in `texts.py` keyed by `action_<key>`
so they can be localized. This module only holds the model instructions, which
are language-agnostic (the model replies in the language of the source text).
"""

from __future__ import annotations

# All text actions (used for routing/quota in execute.py — order-independent).
TEXT_ACTION_KEYS = ["summary", "structure", "reply", "email", "items", "translate"]
CUSTOM_KEY = "custom"

# Inline-keyboard layout: the text actions shown in the action grid. PDF /
# presentation / image are feature-flagged off, so the grid is text-only.
PRIMARY_ACTION_KEYS = ["summary", "structure", "reply", "email", "items", "translate"]


def label_key(action_key: str) -> str:
    """texts.py key for an action's button label."""
    return f"action_{action_key}"


# Appended to every predefined prompt so the model uses the sender names that
# appear in the labeled context (e.g. "[1] Иван Петров (voice → transcript): …").
NAME_INSTRUCTION = (
    "When referring to people, use their names exactly as labeled in the context. "
)

# Answer-language rule appended to every action prompt and the custom wrapper.
# The answer content follows the SOURCE messages, not the user's UI language.
SOURCE_LANG_INSTRUCTION = (
    "Respond in the same language as the source messages above, unless the "
    "instruction explicitly requests a different language. "
)

# Plain-text rule: answers go straight into a chat, so no Markdown by default.
PLAIN_TEXT_INSTRUCTION = (
    "Write in plain prose. Do NOT use any Markdown: no '#' headings, no '*'/'_' "
    "for bold or italic, no backticks or code fences, no '-'/'*' bullet markers, "
    "no tables. Separate paragraphs with a blank line; if a list is unavoidable, "
    "put each item on its own line, optionally starting with '• '. "
)

# Shared tail for predefined text actions.
_COMMON = (
    NAME_INSTRUCTION
    + SOURCE_LANG_INSTRUCTION
    + PLAIN_TEXT_INSTRUCTION
    + "Rely only on the provided text and do not invent facts."
)

# --- Predefined text actions -------------------------------------------------
SYSTEM_PROMPTS: dict[str, str] = {
    "summary": (
        "You make concise, accurate summaries. Read the combined batch of "
        "messages and produce a coherent summary of the key points. " + _COMMON
    ),
    "structure": (
        "You bring order to text. Reorganize the combined batch into a clean "
        "structure: headings, nested bullet points and lists, keeping all "
        "essential details. " + _COMMON
    ),
    "reply": (
        "You write replies in a conversation. Based on the messages, draft a "
        "polite, appropriate reply to whoever sent them. " + _COMMON
    ),
    "email": (
        "You write business emails. Compose a follow-up email based on these "
        "messages: subject line, greeting, a short recap of agreements, and "
        "next steps. " + _COMMON
    ),
    "items": (
        "You are an analyst. Extract concrete tasks, decisions and owners from "
        "the text. Output a list in the form 'Task — Owner — Due (if any)', then "
        "list the decisions separately. " + _COMMON
    ),
    "translate": (
        "You are a professional translator. Translate the entire combined text "
        "into English, preserving meaning and tone. If there are service labels "
        "like '[1] Name (...)', translate only the content part. "
        + NAME_INSTRUCTION + SOURCE_LANG_INSTRUCTION + PLAIN_TEXT_INSTRUCTION
    ),
}

# --- Special generators ------------------------------------------------------
# Presentation: must return JSON only (parsed by pptx_builder).
# Palette names the planner may choose from (hex lives in deck_design.py).
DECK_PALETTES = [
    "Midnight Executive", "Teal Trust", "Forest & Moss", "Coral Energy",
    "Ocean Gradient", "Charcoal Minimal", "Berry & Cream", "Cherry Bold",
]

# Rich deck planner: returns a design plan (layouts + palette), not raw text.
DECK_PLAN_SYSTEM = (
    "You are a senior presentation designer. Read the combined batch and design a "
    "deck. Return JSON ONLY — no markdown fences, no preamble.\n"
    'Shape: {"palette": "<one palette name>", "slides": [ <slide objects> ]}\n'
    "Each slide is one of these layouts (set \"layout\" accordingly):\n"
    '- {"layout":"title","title":"...","subtitle":"..."}\n'
    '- {"layout":"agenda","title":"...","items":["..."]}\n'
    '- {"layout":"section","title":"..."}\n'
    '- {"layout":"bullets","title":"...","bullets":["..."]}\n'
    '- {"layout":"two_column","title":"...","bullets":["..."],"image_ref":1}\n'
    '- {"layout":"image_feature","title":"...","caption":"...","image_ref":2}\n'
    '- {"layout":"stat","title":"...","stats":[{"value":"42%","label":"..."}]}\n'
    '- {"layout":"comparison","title":"...","columns":[{"heading":"Before","items":["..."]},'
    '{"heading":"After","items":["..."]}]}\n'
    '- {"layout":"quote","quote":"...","attribution":"..."}\n'
    "Rules: open with a title slide; add an agenda or section divider early; VARY "
    "layouts (do NOT use bullets on every slide); use stat for numbers, comparison "
    "for before/after or options, quote for one strong line, two_column or "
    "image_feature where a forwarded photo fits; close with a section-style slide. "
    "Max 5 items/bullets per slide, each <= ~12 words. Write specific slide titles "
    "(never 'Slide 1' or 'Images'). Pick exactly one palette from this list that "
    "fits the topic: " + ", ".join(DECK_PALETTES) + ". "
    "image_ref is OPTIONAL: set it to an available photo id (tagged '[photo #N]' / "
    "listed under 'AVAILABLE PHOTOS') when an image strengthens the slide, "
    "especially if the instruction asks to include the photos; otherwise omit it. "
    + NAME_INSTRUCTION + SOURCE_LANG_INSTRUCTION
)

# Vision QA: detect visual defects on a rendered slide image. JSON only.
DECK_QA_SYSTEM = (
    "You are a meticulous presentation QA reviewer. You are shown ONE rendered "
    "slide image. Report only real, user-visible layout defects. Return JSON ONLY:\n"
    '{"slide": <n>, "issues": [{"type":"...","element":"...","severity":"low|med|high"}]}\n'
    "Allowed type values: overflow (text cut off at a box or slide edge), overlap "
    "(elements on top of each other), low_contrast (text hard to read on its "
    "background), narrow_wrap (text wrapping awkwardly in a too-narrow box), "
    "small_margin (element too close to the slide edge). element is one of: title, "
    "body, image, stat, slide. If the slide looks clean, return an empty issues "
    "list. Do not invent defects."
)

# PDF: structured plain-text document parsed line-by-line by pdf_builder.
PDF_SYSTEM = (
    "You produce a clean, structured document as plain UTF-8 text. Use '# ' for "
    "main headings, '## ' for subheadings, '- ' for bullet points, and blank "
    "lines between blocks. No markdown tables, no code fences. " + NAME_INSTRUCTION
    + SOURCE_LANG_INSTRUCTION
)

# Image: returns ONLY a vivid prompt string for the image model.
IMAGE_PROMPT_SYSTEM = (
    "Based on the combined batch, write a single concise, vivid image-generation "
    "prompt (max 200 words) in English. Return ONLY the prompt text — no quotes, "
    "no preamble, no explanation."
)

# Custom free-text instruction.
CUSTOM_SYSTEM = (
    "You are a versatile assistant. You receive the combined batch of messages, "
    "the user's instruction, and possibly extra context (from files or links). "
    "Follow the instruction precisely, grounded in the provided materials. "
    + _COMMON
)

# --- Group mode --------------------------------------------------------------
# Each is fed a transcript of recent group messages as "Name: text" lines.
_GROUP_COMMON = (
    "You are summarizing a group chat. Respond in the dominant language of the "
    "messages. Attribute points to the named people. Be concise and factual; "
    "rely only on the provided messages. " + PLAIN_TEXT_INSTRUCTION
)
GROUP_SUMMARY_SYSTEM = (
    _GROUP_COMMON
    + "Produce a short recap: who raised what, proposals, decisions, and open "
    "questions (e.g. 'Ivan raised X; Maria proposed Y; decision: Z; open: W')."
)
GROUP_ASK_SYSTEM = (
    _GROUP_COMMON
    + "Answer the user's question (given after the messages) using only what was "
    "said in the thread. If the thread doesn't cover it, say so."
)
GROUP_ACTIONS_SYSTEM = (
    _GROUP_COMMON
    + "Extract concrete action items and decisions as a list in the form "
    "'Task — Owner — Due (if any)', then list decisions separately."
)

# Sent alongside each photo to the vision model.
VISION_PROMPT = (
    "Extract all text from this image verbatim (preserve the original language). "
    "Then add a single short line describing what the image shows. Format as:\n"
    "TEXT:\n<verbatim text or '—' if none>\nDESCRIPTION: <one line>"
)
