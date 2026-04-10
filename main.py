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
                    "SELECT order_id, external_order_id, user_id, quantity, price, comment, link "
                    "FROM orders WHERE status = 'PROCESSING' AND external_provider = 'vexboost'"
                )
                processing_orders = await cursor.fetchall()
            if processing_orders:
                # Группируем ID для одного запроса (максимум 10-20 за раз)
                ids = [row[1] for row in processing_orders if row[1] is not None]
                if ids:
                    chunk_size = 10
                    for i in range(0, len(ids), chunk_size):
                        chunk = ids[i:i+chunk_size]
                        statuses = await get_orders_status(chunk)
                        for order in processing_orders:
                            order_id = order[0]
                            ext_id = order[1]
                            user_id = order[2]
                            quantity = order[3]
                            price = order[4]
                            comment = order[5]
                            link = order[6]
                            if str(ext_id) in statuses:
                                ext_data = statuses[str(ext_id)]
                                if isinstance(ext_data, dict):
                                    ext_status = ext_data.get('status')
                                    remains = int(ext_data.get('remains', 0))
                                    charge = float(ext_data.get('charge', 0))

                                    if ext_status == 'Completed':
                                        # Заказ выполнен полностью
                                        await db.update_order_status(order_id, "PAID", "Выполнено через VexBoost")
                                        await bot.send_message(
                                            user_id,
                                            f"✅ Ваш заказ №{order_id} выполнен!\n\n"
                                            f"📦 Услуга: {comment}\n"
                                            f"🔢 Количество: {quantity}\n"
                                            f"💰 Сумма: {price:.2f} руб.\n"
                                            f"🔗 Ссылка: {link}"
                                        )
                                    elif ext_status == 'In progress':
                                        # Заказ ещё выполняется – ничего не делаем
                                        pass
                                    elif ext_status == 'Awaiting':
                                        # Заказ ожидает обработки – ничего не делаем
                                        pass
                                    elif ext_status == 'Canceled':
                                        # Заказ отменён. Если что-то накручено, возвращаем только за недокрученное
                                        if remains > 0:
                                            # Считаем, что выполнено (quantity - remains)
                                            completed_qty = quantity - remains
                                            # Стоимость выполненных (пропорционально)
                                            completed_price = (completed_qty / quantity) * price
                                            refund = price - completed_price
                                            if refund > 0:
                                                await db.update_balance(user_id, refund)
                                                await db.update_order_status(order_id, "DECLINED", f"Частично выполнен (VexBoost Canceled). Возвращено {refund:.2f} руб.")
                                                await bot.send_message(
                                                    user_id,
                                                    f"⚠️ Заказ №{order_id} отменён частично.\n"
                                                    f"Выполнено: {completed_qty} из {quantity}\n"
                                                    f"Возвращено: {refund:.2f} руб.\n"
                                                    f"Списано: {completed_price:.2f} руб."
                                                )
                                            else:
                                                # Ничего не выполнено – полный возврат
                                                await db.update_balance(user_id, price)
                                                await db.update_order_status(order_id, "DECLINED", "Отменён VexBoost (Canceled). Полный возврат.")
                                                await bot.send_message(user_id, f"❌ Заказ №{order_id} отменён. Средства полностью возвращены.")
                                        else:
                                            # Ничего не выполнено
                                            await db.update_balance(user_id, price)
                                            await db.update_order_status(order_id, "DECLINED", "Отменён VexBoost (Canceled). Полный возврат.")
                                            await bot.send_message(user_id, f"❌ Заказ №{order_id} отменён. Средства возвращены.")
                                    elif ext_status == 'Fail':
                                        # Полный возврат
                                        await db.update_balance(user_id, price)
                                        await db.update_order_status(order_id, "DECLINED", "Неудачный заказ (VexBoost Fail)")
                                        await bot.send_message(
                                            user_id,
                                            f"❌ Заказ №{order_id} не выполнен (ошибка). Средства возвращены полностью.\n\n"
                                            f"📦 Услуга: {comment}\n"
                                            f"🔢 Количество: {quantity}\n"
                                            f"🔗 Ссылка: {link}"
                                        )
                                    elif ext_status == 'Partial':
                                        # Частично выполнен – возврат за остаток
                                        if remains > 0:
                                            completed_qty = quantity - remains
                                            completed_price = (completed_qty / quantity) * price
                                            refund = price - completed_price
                                            if refund > 0:
                                                await db.update_balance(user_id, refund)
                                                await db.update_order_status(order_id, "PAID", f"Частично выполнен (VexBoost Partial). Возвращено {refund:.2f} руб.")
                                                await bot.send_message(
                                                    user_id,
                                                    f"⚠️ Заказ №{order_id} выполнен частично.\n"
                                                    f"Выполнено: {completed_qty} из {quantity}\n"
                                                    f"Возвращено: {refund:.2f} руб.\n"
                                                    f"Списано: {completed_price:.2f} руб."
                                                )
                                            else:
                                                # ничего не выполнено
                                                await db.update_balance(user_id, price)
                                                await db.update_order_status(order_id, "DECLINED", "Частичный возврат не удался? Полный возврат")
                                                await bot.send_message(user_id, f"❌ Заказ №{order_id} не выполнен. Средства возвращены.")
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