import asyncio
import logging
import sys

from aiohttp import ClientError
from aiogram import Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from bot_session import create_bot
from config import BOT_TOKEN, DEV_MODE
from database import init_db
from handlers import router
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

RETRY_DELAY_SEC = 5
MAX_RETRY_DELAY_SEC = 60


async def main() -> None:
    if not BOT_TOKEN:
        if DEV_MODE:
            logger.error(
                "DEV=1 but BOT_TOKEN_DEV is empty. Create a dev bot in @BotFather "
                "and set BOT_TOKEN_DEV in .env. See LOCAL_DEV.md"
            )
        else:
            logger.error("BOT_TOKEN is not set. Copy .env.example to .env and fill BOT_TOKEN.")
        sys.exit(1)

    if DEV_MODE:
        logger.info("DEV mode: local bot, database %s", "data/bot_dev.db")
    else:
        logger.info("Production mode (set DEV=1 in .env for local development)")

    await init_db()

    bot = create_bot()
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started (daily job at 09:00 MSK)")

    try:
        retry_delay = RETRY_DELAY_SEC
        fail_count = 0
        while True:
            try:
                logger.info("Connecting to Telegram...")
                await dp.start_polling(bot, handle_signals=False)
                break
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except (OSError, ClientError, TelegramNetworkError, asyncio.TimeoutError) as exc:
                fail_count += 1
                logger.error(
                    "Network error (%s). Retry in %s sec (#%s).",
                    exc,
                    retry_delay,
                    fail_count,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY_SEC)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
