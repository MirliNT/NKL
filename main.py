import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from middlewares.ban_check import BanCheckMiddleware
from middlewares.bot_status import BotStatusMiddleware
from handlers import start, order, balance, admin, payment, common
from database.core import init_db
from utils.cache import get_admins

# Настройка логирования
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/bot.log', maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting bot...")

    # Инициализация базы данных
    await init_db()
    logger.info("Database initialized")

    # Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация middleware
    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())
    dp.message.middleware(BotStatusMiddleware())
    dp.callback_query.middleware(BotStatusMiddleware())
    logger.info("Middleware registered")

    # Подключение роутеров
    dp.include_router(start.router)
    dp.include_router(order.router)
    dp.include_router(balance.router)
    dp.include_router(admin.router)
    dp.include_router(payment.router)
    dp.include_router(common.router)
    logger.info("Routers included")

    # Предварительная загрузка кэша (админы)
    await get_admins()
    logger.info("Cache warmed up")

    # Запуск поллинга
    logger.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())