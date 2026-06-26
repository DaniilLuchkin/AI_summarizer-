"""Bot command menu definitions, shared by main.py and handlers/commands.py.

Kept in its own module so both can import it without a circular import.
"""

from __future__ import annotations

from aiogram.types import BotCommand

# Commands shown in group chats (registered with BotCommandScopeAllGroupChats).
GROUP_COMMANDS: dict[str, list[BotCommand]] = {
    "en": [
        BotCommand(command="summary", description="Summarize recent messages"),
        BotCommand(command="ask", description="Ask about the recent thread (Pro)"),
        BotCommand(command="actions", description="Action items from the thread (Pro)"),
        BotCommand(command="clear", description="Clear my buffer (admins)"),
    ],
    "ru": [
        BotCommand(command="summary", description="Кратко о последних сообщениях"),
        BotCommand(command="ask", description="Вопрос по треду (Pro)"),
        BotCommand(command="actions", description="Задачи из треда (Pro)"),
        BotCommand(command="clear", description="Очистить буфер (админы)"),
    ],
    "uk": [
        BotCommand(command="summary", description="Стисло про останні повідомлення"),
        BotCommand(command="ask", description="Питання по треду (Pro)"),
        BotCommand(command="actions", description="Завдання з треду (Pro)"),
        BotCommand(command="clear", description="Очистити буфер (адміни)"),
    ],
}

COMMANDS: dict[str, list[BotCommand]] = {
    "en": [
        BotCommand(command="start", description="What this bot does"),
        BotCommand(command="reset", description="Clear the current batch"),
        BotCommand(command="pro", description="Upgrade to Pro"),
        BotCommand(command="plans", description="Plans & pricing"),
        BotCommand(command="usage", description="Your usage & limits"),
        BotCommand(command="help", description="How it works"),
        BotCommand(command="lang", description="Change interface language"),
    ],
    "ru": [
        BotCommand(command="start", description="Что умеет бот"),
        BotCommand(command="reset", description="Очистить текущую пачку"),
        BotCommand(command="pro", description="Перейти на Pro"),
        BotCommand(command="plans", description="Тарифы и цены"),
        BotCommand(command="usage", description="Лимиты и использование"),
        BotCommand(command="help", description="Как это работает"),
        BotCommand(command="lang", description="Сменить язык интерфейса"),
    ],
    "uk": [
        BotCommand(command="start", description="Що вміє бот"),
        BotCommand(command="reset", description="Очистити поточну пачку"),
        BotCommand(command="pro", description="Перейти на Pro"),
        BotCommand(command="plans", description="Тарифи та ціни"),
        BotCommand(command="usage", description="Ліміти та використання"),
        BotCommand(command="help", description="Як це працює"),
        BotCommand(command="lang", description="Змінити мову інтерфейсу"),
    ],
}
