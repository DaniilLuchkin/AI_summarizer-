"""Bot command menu definitions, shared by main.py and handlers/commands.py.

Kept in its own module so both can import it without a circular import.
"""

from __future__ import annotations

from aiogram.types import BotCommand

COMMANDS: dict[str, list[BotCommand]] = {
    "en": [
        BotCommand(command="start", description="What this bot does"),
        BotCommand(command="reset", description="Clear the current batch"),
        BotCommand(command="help", description="How it works"),
        BotCommand(command="lang", description="Change interface language"),
    ],
    "ru": [
        BotCommand(command="start", description="Что умеет бот"),
        BotCommand(command="reset", description="Очистить текущую пачку"),
        BotCommand(command="help", description="Как это работает"),
        BotCommand(command="lang", description="Сменить язык интерфейса"),
    ],
    "uk": [
        BotCommand(command="start", description="Що вміє бот"),
        BotCommand(command="reset", description="Очистити поточну пачку"),
        BotCommand(command="help", description="Як це працює"),
        BotCommand(command="lang", description="Змінити мову інтерфейсу"),
    ],
}
