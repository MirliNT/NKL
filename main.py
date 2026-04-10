import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, DB_PATH
from bot_instance import bot
from middlewares import BanCheckMiddleware, BotStatusMiddleware
from handlers import start_router, order_router, balance_router, admin_router, payment_router, common_router
from database.core import init_db
from utils.cache import get_admins
from utils.vexboost import get_orders_status
import database as db

logger = logging.getLogger(__name__)

# ====== Фоновая задача для проверки заказов VexBoost ======
async def check_vexboost_orders():
    """Периодически проверяет статусы заказов, переданных в VexBoost."""
    while True:
        try:
            # Получаем заказы со статусом PROCESSING и external_provider = 'vexboost'
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.execute(
                    "SELECT order_id, external_order_id, user_id, quantity, price, comment "
                    "FROM orders WHERE status = 'PROCESSING' AND external_provider = 'vexboost'"
                )
                processing_orders = await cursor.fetchall()
            if processing_orders:
                # Группируем ID для одного запроса (максимум 10-20 за раз)
                ids = [row[1] for row in processing_orders if row[1] is not None]
                if ids:
                    # Разбиваем на части по 10 (ограничение API не указано, но для безопасности)
                    chunk_size = 10
                    for i in range(0, len(ids), chunk_size):
                        chunk = ids[i:i+chunk_size]
                        statuses = await get_orders_status(chunk)
                        for order in processing_orders:
                            ext_id = order[1]
                            if str(ext_id) in statuses:
                                ext_data = statuses[str(ext_id)]
                                if isinstance(ext_data, dict):
                                    ext_status = ext_data.get('status')
                                    order_id = order[0]
                                    user_id = order[2]
                                    if ext_status == 'Completed':
                                        await db.update_order_status(order_id, "PAID", "Выполнено через VexBoost")
                                        await bot.send_message(user_id, f"✅ Ваш заказ №{order_id} выполнен!")
                                    elif ext_status in ('Canceled', 'Fail'):
                                        # Возвращаем средства
                                        price = order[4]
                                        await db.update_balance(user_id, price)
                                        await db.update_order_status(order_id, "DECLINED", f"Отменён VexBoost: {ext_status}")
                                        await bot.send_message(user_id, f"❌ Заказ №{order_id} не выполнен. Средства возвращены.")
                                    # Остальные статусы (Partial, In progress) игнорируем
            await asyncio.sleep(300)  # 5 минут
        except Exception as e:
            logger.error(f"VexBoost status check error: {e}")
            await asyncio.sleep(60)

# ====== Основная функция ======
async def main():
    logger.info("Starting bot...")
    await init_db()
    logger.info("Database initialized")

    # Регистрация middleware
    dp = Dispatcher()
    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())
    dp.message.middleware(BotStatusMiddleware())
    dp.callback_query.middleware(BotStatusMiddleware())
    logger.info("Middleware registered")

    # Подключение роутеров
    dp.include_router(start_router)
    dp.include_router(order_router)
    dp.include_router(balance_router)
    dp.include_router(admin_router)
    dp.include_router(payment_router)
    dp.include_router(common_router)
    logger.info("Routers included")

    # Предварительная загрузка кэша (админы)
    await get_admins()
    logger.info("Cache warmed up")

    # Запуск фоновой задачи для VexBoost
    asyncio.create_task(check_vexboost_orders())

    logger.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())