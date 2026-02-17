"""
Main entry point for Greek Learning Bot.
"""

import asyncio
import signal
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.config import config
from bot.database.database import init_db, close_db
from bot.middlewares.user_middleware import UserMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.handlers import start, lessons, difficulty, practice, review, statistics, settings
from bot.utils.logger import logger


async def main():
    """Main function to start the bot."""
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    
    # Register middlewares
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.5))
    
    # Register routers
    dp.include_router(start.router)
    dp.include_router(lessons.router)
    dp.include_router(difficulty.router)
    dp.include_router(practice.router)
    dp.include_router(review.router)
    dp.include_router(statistics.router)
    dp.include_router(settings.router)
    
    # Initialize database
    try:
        await init_db()
        logger.info("Bot starting...")
        
        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
    finally:
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    raise KeyboardInterrupt


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
