"""System prompts for predefined actions + special generators.

Button labels are NOT here — they live in `texts.py` keyed by `action_<key>`
so they can be localized. This module only holds the model instructions, which
are language-agnostic (the model replies in the language of the source text).
"""

from __future__ import annotations

# Order of buttons on the inline keyboard.
TEXT_ACTION_KEYS = ["summary", "structure", "reply", "email", "items", "translate"]
SPECIAL_ACTION_KEYS = ["presentation", "pdf", "image"]
CUSTOM_KEY = "custom"
KEYBOARD_ORDER = TEXT_ACTION_KEYS + SPECIAL_ACTION_KEYS + [CUSTOM_KEY]


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

# Shared tail for predefined text actions.
_COMMON = (
    NAME_INSTRUCTION
    + SOURCE_LANG_INSTRUCTION
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
        "into English, preserving meaning, tone and formatting. If there are "
        "service labels like '[1] Name (...)', translate only the content part. "
        + NAME_INSTRUCTION + SOURCE_LANG_INSTRUCTION
    ),
}

# --- Special generators ------------------------------------------------------
# Presentation: must return JSON only (parsed by pptx_builder).
PRESENTATION_SYSTEM = (
    "You design slide decks. Read the combined batch and return a presentation "
    "as JSON ONLY — no markdown fences, no preamble, no trailing text. Shape:\n"
    '{"title": "Presentation title", "slides": [{"title": "Slide title", '
    '"bullets": ["point 1", "point 2"]}]}\n'
    "Produce 5–10 slides capturing the key ideas. " + NAME_INSTRUCTION
    + SOURCE_LANG_INSTRUCTION
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
    "rely only on the provided messages. "
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
