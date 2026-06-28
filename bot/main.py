"""Bot entry point: build settings, wire services + handlers, start long polling.

Run with:  python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram.types import BotCommandScopeAllGroupChats

from bot.commands_menu import COMMANDS, GROUP_COMMANDS
from bot.config import Settings
from bot.handlers import account, actions, billing, collect, commands, group
from bot.handlers import models as models_handler
from bot.middleware import AccessMiddleware
from bot.runtime import AppContext
from bot.services.batch import BatchStore
from bot.services.credits import CreditService
from bot.services.db import Database
from bot.services.group_buffer import GroupBuffer
from bot.services.models import ModelService
from bot.services.openrouter import OpenRouterClient
from bot.services.quota import Quota
from bot.services.ratelimit import RateLimiter

logger = logging.getLogger(__name__)


def build_dispatcher(ctx: AppContext) -> Dispatcher:
    """Create the dispatcher, register the access middleware and all routers.

    Router order matters: commands first (so /start, /reset win in any state),
    then billing (so successful_payment messages are consumed before the
    catch-all collector), account, actions, then the collector last.
    """
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(AccessMiddleware(ctx.settings))

    dp.include_router(commands.build_router(ctx))
    dp.include_router(billing.build_router(ctx))
    dp.include_router(account.build_router(ctx))
    dp.include_router(models_handler.build_router(ctx))
    dp.include_router(group.build_router(ctx))  # group-only; before the collector
    dp.include_router(actions.build_router(ctx))
    dp.include_router(collect.build_router(ctx))
    return dp


async def _run() -> None:
    settings = Settings()  # type: ignore[call-arg]  # values come from env
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required (add the Railway Postgres plugin)")

    db = Database()
    await db.connect(settings.database_url)

    orclient = OpenRouterClient(settings)
    quota = Quota(db, settings)
    ctx = AppContext(
        settings=settings,
        store=BatchStore(settings.max_batch_messages, settings.max_context_chars),
        limiter=RateLimiter(settings.max_batches_per_hour),
        orclient=orclient,
        db=db,
        quota=quota,
        credits=CreditService(db, settings),
        group_buffer=GroupBuffer(settings.group_buffer_max, settings.group_buffer_ttl_hours),
        models=ModelService(db, settings, orclient, quota),
    )

    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties())
    dp = build_dispatcher(ctx)

    logger.info("Starting polling (public=%s)", not settings.allowed_ids)
    try:
        # Drop any updates queued while the bot was offline.
        await bot.delete_webhook(drop_pending_updates=True)
        await setup_commands(bot)
        await dp.start_polling(bot)
    finally:
        await orclient.aclose()
        await db.close()
        await bot.session.close()


async def setup_commands(bot: Bot) -> None:
    """Register the command menu: a default (English) plus per-language scopes.

    A user's client shows the menu for their Telegram language; /lang overrides
    it per chat (see handlers/commands.py).
    """
    await bot.set_my_commands(COMMANDS["en"])  # default (private) fallback menu
    for code in ("ru", "uk", "en"):
        await bot.set_my_commands(COMMANDS[code], language_code=code)

    # Group-scope menu (separate from the private-chat menu).
    group_scope = BotCommandScopeAllGroupChats()
    await bot.set_my_commands(GROUP_COMMANDS["en"], scope=group_scope)
    for code in ("ru", "uk", "en"):
        await bot.set_my_commands(GROUP_COMMANDS[code], scope=group_scope, language_code=code)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
