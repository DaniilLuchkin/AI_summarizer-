"""Bot entry point: build settings, wire services + handlers, start long polling.

Run with:  python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Settings
from bot.handlers import actions, collect, commands
from bot.middleware import AccessMiddleware
from bot.runtime import AppContext
from bot.services.batch import BatchStore
from bot.services.openrouter import OpenRouterClient
from bot.services.ratelimit import RateLimiter

logger = logging.getLogger(__name__)


def build_dispatcher(ctx: AppContext) -> Dispatcher:
    """Create the dispatcher, register the access middleware and all routers.

    Router order matters: commands first (so /start, /reset win in any state),
    then the actions router (callbacks + the staged-input state), then the
    catch-all collector (which only runs in the default state).
    """
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(AccessMiddleware(ctx.settings))

    dp.include_router(commands.build_router(ctx))
    dp.include_router(actions.build_router(ctx))
    dp.include_router(collect.build_router(ctx))
    return dp


async def _run() -> None:
    settings = Settings()  # type: ignore[call-arg]  # values come from env
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    orclient = OpenRouterClient(settings)
    ctx = AppContext(
        settings=settings,
        store=BatchStore(settings.max_batch_messages, settings.max_context_chars),
        limiter=RateLimiter(settings.max_batches_per_hour, settings.max_llm_calls_per_day),
        orclient=orclient,
    )

    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties())
    dp = build_dispatcher(ctx)

    logger.info("Starting polling (public=%s)", not settings.allowed_ids)
    try:
        # Drop any updates queued while the bot was offline.
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await orclient.aclose()
        await bot.session.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
