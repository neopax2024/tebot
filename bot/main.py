"""
Bot entry point — supports both polling (dev) and webhook (prod).

Usage
-----
  python -m bot.main          # polling mode
  BOT_TOKEN=... WEBHOOK_URL=https://... python -m bot.main   # webhook
"""

from __future__ import annotations

import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import settings
from config.logging_config import setup_logging
from database.engine import init_db
from scanner.analyzer import close_session as close_analyzer_session

# Handlers
from bot.handlers import start, scan, generate, dynamic, history, account, admin

# Middlewares
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares (order matters — auth runs first)
    dp.update.middleware(AuthMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    # Include routers
    dp.include_router(start.router)
    dp.include_router(scan.router)
    dp.include_router(generate.router)
    dp.include_router(dynamic.router)
    dp.include_router(history.router)
    dp.include_router(account.router)
    dp.include_router(admin.router)

    return dp


async def on_startup(bot: Bot) -> None:
    await init_db()
    logger.info("Database tables verified / created.")

    if settings.WEBHOOK_URL:
        webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}{settings.WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info("Webhook set to %s", webhook_url)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Polling mode — webhook removed.")

    me = await bot.get_me()
    logger.info("Bot started: @%s (%s)", me.username, me.full_name)


async def on_shutdown(bot: Bot) -> None:
    await close_analyzer_session()
    logger.info("Bot shutting down.")


async def run_polling() -> None:
    setup_logging()
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()

    dp.startup.register(lambda: on_startup(bot))
    dp.shutdown.register(lambda: on_shutdown(bot))

    logger.info("Starting polling…")
    await dp.start_polling(bot)


async def run_webhook() -> None:
    setup_logging()
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()

    await on_startup(bot)

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.API_HOST, settings.API_PORT)
    await site.start()
    logger.info(
        "Webhook server listening on %s:%s%s",
        settings.API_HOST,
        settings.API_PORT,
        settings.WEBHOOK_PATH,
    )

    # Keep running until SIGTERM / SIGINT
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    await runner.cleanup()
    await on_shutdown(bot)


def main() -> None:
    if settings.WEBHOOK_URL:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
