import asyncio
import logging
import sys
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from app.config import settings
from app.database import db
from app.bot.handlers import router as bot_router
from app.web.server import app as fastapi_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


async def run_fastapi(server: uvicorn.Server) -> None:
    """Run uvicorn server inside the asyncio event loop."""
    logger.info("Starting FastAPI WebApp server on http://%s:%s", settings.SERVER_HOST, settings.SERVER_PORT)
    try:
        await server.serve()
    except asyncio.CancelledError:
        logger.info("FastAPI WebApp server cancelled")


async def run_bot(bot: Bot, dp: Dispatcher) -> None:
    """Run aiogram bot polling with reliable connection timeouts."""
    logger.info("Starting Telegram Bot long-polling...")
    try:
        # Drop pending updates on startup to prevent stale backlogs
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, polling_timeout=20)
    except asyncio.CancelledError:
        logger.info("Telegram Bot polling cancelled")
    except Exception as exc:
        logger.exception("Unexpected error in Telegram bot polling: %s", exc)
    finally:
        await bot.session.close()
        logger.info("Telegram Bot session closed")


async def main() -> None:
    """Application entry point: initializes DB and runs FastAPI & Bot concurrently."""
    logger.info("Initializing database...")
    await db.init_db()
    origin = await db.get_origin()
    logger.info("Current Origin Point A: %s (lat: %s, lon: %s)", origin.get("name"), origin.get("lat"), origin.get("lon"))

    # Configure Uvicorn server
    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)

    # Check bot token
    if not settings.BOT_TOKEN or "example" in settings.BOT_TOKEN or len(settings.BOT_TOKEN) < 15:
        logger.warning(
            "⚠️ BOT_TOKEN is not configured or contains placeholder in .env! "
            "Telegram bot polling will NOT start. FastAPI Mini App is running alone for testing at http://localhost:%s",
            settings.SERVER_PORT,
        )
        await server.serve()
        return

    # Use AiohttpSession with generous timeout (120s) to prevent request timeout errors
    session = AiohttpSession(timeout=120.0)
    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(bot_router)

    # Run both background tasks in single asyncio loop
    server_task = asyncio.create_task(run_fastapi(server))
    bot_task = asyncio.create_task(run_bot(bot, dp))

    try:
        await asyncio.gather(server_task, bot_task)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received")
    finally:
        server.should_exit = True
        server_task.cancel()
        bot_task.cancel()
        await asyncio.gather(server_task, bot_task, return_exceptions=True)
        logger.info("Application stopped gracefully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process terminated by user")
