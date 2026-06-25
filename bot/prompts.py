"""System prompts for predefined actions plus the vision/custom prompts.

Centralized here so the bot's "behaviour" is easy to tweak without touching
handler logic. Each `Action` maps to one inline-keyboard button.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    key: str          # short id, used in callback_data (must stay < 64 bytes)
    label: str        # button text shown to the user (Russian, with emoji)
    system_prompt: str  # system message sent to the LLM for this action


# A shared instruction appended to every action so the model answers in the
# language of the source material and stays grounded in the provided text.
_COMMON = (
    "Отвечай на языке исходного материала (если материал на русском — по-русски, "
    "на украинском — украинским, на английском — английским). "
    "Опирайся только на предоставленный текст и не выдумывай фактов."
)

ACTIONS: list[Action] = [
    Action(
        key="summary",
        label="📝 Краткое содержание",
        system_prompt=(
            "Ты помощник, который делает сжатые и точные резюме. "
            "Прочитай объединённый текст пачки сообщений и составь связное краткое "
            "содержание ключевых мыслей. " + _COMMON
        ),
    ),
    Action(
        key="structure",
        label="🗂 Структурировать",
        system_prompt=(
            "Ты помощник, который наводит порядок в тексте. "
            "Преобразуй объединённый текст в чистую структуру: заголовки, "
            "вложенные пункты и списки. Сохрани все существенные детали. " + _COMMON
        ),
    ),
    Action(
        key="reply",
        label="💬 Черновик ответа",
        system_prompt=(
            "Ты помощник, который пишет ответы в переписке. "
            "На основе сообщений составь вежливый и уместный черновик ответа "
            "тому, кто их прислал. Сохрани деловой, но человеческий тон. " + _COMMON
        ),
    ),
    Action(
        key="email",
        label="✉️ Follow-up письмо",
        system_prompt=(
            "Ты помощник, который пишет деловые письма. "
            "Составь follow-up письмо по итогам этих сообщений: с темой, "
            "приветствием, кратким содержанием договорённостей и следующими шагами. "
            + _COMMON
        ),
    ),
    Action(
        key="actions",
        label="✅ Задачи и решения",
        system_prompt=(
            "Ты помощник-аналитик. Извлеки из текста конкретные задачи, "
            "принятые решения и ответственных. Выведи списком в формате "
            "«Задача — Ответственный — Срок (если есть)». Отдельно перечисли решения. "
            + _COMMON
        ),
    ),
    Action(
        key="translate",
        label="🌐 Перевести (EN)",
        system_prompt=(
            "Ты профессиональный переводчик. Переведи весь объединённый текст "
            "на английский язык, сохраняя смысл, тон и форматирование. "
            "Если в тексте есть служебные пометки вида «[1] (...):», "
            "переводи только содержательную часть."
        ),
    ),
]

# Index actions by key for quick lookup in handlers.
ACTIONS_BY_KEY: dict[str, Action] = {a.key: a for a in ACTIONS}

# Special non-action button: free-text instruction.
CUSTOM_KEY = "custom"
CUSTOM_LABEL = "✍️ Свой запрос"

# System prompt used when the user types their own instruction.
CUSTOM_SYSTEM = (
    "Ты универсальный ассистент. Тебе дают объединённый текст пачки сообщений, "
    "инструкцию пользователя и, возможно, дополнительный контекст (из файлов или "
    "ссылок). Выполни инструкцию максимально точно, опираясь на предоставленные "
    "материалы. " + _COMMON
)

# Prompt sent alongside each photo to the vision model.
VISION_PROMPT = (
    "Extract all text from this image verbatim (preserve the original language). "
    "Then add a single short line describing what the image shows. "
    "Format strictly as:\nTEXT:\n<verbatim text or '—' if none>\nDESCRIPTION: <one line>"
)
