import aiosqlite
import logging
import uuid
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_instance import bot
from config import DB_PATH
from states.states import BalanceTopup
import database as db
from utils.payments import create_yookassa_payment, create_heleket_payment, check_yookassa_payment, check_heleket_payment

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "balance")
async def balance_menu(call: CallbackQuery):
    await call.answer()
    balance = await db.get_balance(call.from_user.id)
    # Формируем текст с кастомными эмодзи
    text = f"""
<tg-emoji emoji-id="4958926882994127612">💰</tg-emoji><b>Ваш баланс: {balance:.2f} руб.

</b><b><tg-emoji emoji-id="5204330443725347173">⭐️</tg-emoji></b><b>Выберите способ оплаты из списка ниже</b>:
    """
    # Создаём клавиатуру вручную через словарь (чтобы добавить icon_custom_emoji_id)
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "СБП, QR, КАРТА",
                    "callback_data": "topup_yookassa",
                    "icon_custom_emoji_id": "5463197305295373989"
                }
            ],
            [
                {
                    "text": "Криптовалюта",
                    "callback_data": "topup_heleket",
                    "icon_custom_emoji_id": "5452069891139994051"
                }
            ],
            [
                {
                    "text": "Назад",
                    "callback_data": "back_to_main"
                    "icon_custom_emoji_id": "5258236805890710909"
                }
            ]
        ]
    }
    # Отправляем сообщение с клавиатурой через прямой API-вызов (чтобы поддержать иконки)
    import aiohttp
    import json
    from config import BOT_TOKEN
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": call.from_user.id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
            "disable_web_page_preview": True
        }
        # Если нужно заменить предыдущее сообщение, можно сначала удалить
        try:
            await call.message.delete()
        except:
            pass
        await session.post(url, json=payload)

@router.callback_query(F.data == "topup_yookassa")
async def topup_yookassa_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(method="yookassa")
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Отмена", callback_data="balance")
    await call.message.answer(
        "Введите сумму пополнения (от 10.00 руб.):",
        reply_markup=kb.as_markup()
    )
    await state.set_state(BalanceTopup.waiting_amount)

@router.callback_query(F.data == "topup_heleket")
async def topup_heleket_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(method="heleket")
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Отмена", callback_data="balance")
    await call.message.answer(
        "Введите сумму пополнения (от 10.00 руб.):",
        reply_markup=kb.as_markup()
    )
    await state.set_state(BalanceTopup.waiting_amount)

@router.message(BalanceTopup.waiting_amount)
async def topup_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.replace('.', '').isdigit():
        return await message.answer("Введите число (например, 100.50).")
    amount = float(message.text)
    data = await state.get_data()
    method = data.get("method")
    if amount < 10.0:
        return await message.answer("Минимальная сумма пополнения: 10.00 руб.")
    await state.update_data(amount=amount)
    if method == "yookassa":
        await create_yookassa_topup(message, state, amount)
    else:
        await create_heleket_topup(message, state, amount)

async def create_yookassa_topup(message: Message, state: FSMContext, amount: float):
    try:
        payment_data = await create_yookassa_payment(
            amount=amount,
            description=f"Пополнение баланса пользователя {message.from_user.id}",
            order_id=f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}",
            user_id=message.from_user.id
        )
        payment_id = payment_data.get('id')
        confirmation_url = payment_data.get('confirmation', {}).get('confirmation_url')
        if not payment_id or not confirmation_url:
            raise Exception("Missing payment data")
        await db.add_transaction(message.from_user.id, amount, "yookassa", "pending", payment_id)
        kb = InlineKeyboardBuilder()
        kb.button(text="СБП, QR, КАРТА", url=confirmation_url)
        kb.button(text="✅ Проверить оплату", callback_data=f"check_topup_{payment_id}")
        await message.answer(
            f"Создан счёт на пополнение баланса на {amount:.2f} руб.\n"
            "После оплаты нажмите «Проверить оплату».",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Topup error: {e}")
        await message.answer("Не удалось создать платёж. Попробуйте позже.")
        await state.clear()

async def create_heleket_topup(message: Message, state: FSMContext, amount: float):
    try:
        payment_result = await create_heleket_payment(
            amount=amount,
            order_id=f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}",
            description=f"Пополнение баланса на {amount} руб.",
            user_id=message.from_user.id
        )
        payment_uuid = payment_result.get('uuid')
        payment_url = payment_result.get('url')
        if not payment_uuid or not payment_url:
            raise Exception("Missing payment data")
        await db.add_transaction(message.from_user.id, amount, "heleket", "pending", payment_uuid)
        kb = InlineKeyboardBuilder()
        kb.button(text="Оплатить криптовалютой", url=payment_url)
        kb.button(text="✅ Проверить оплату", callback_data=f"check_topup_{payment_uuid}")
        await message.answer(
            f"Создан счёт на пополнение баланса на {amount:.2f} руб.\n"
            "На странице оплаты выберите удобную криптовалюту и сеть.\n"
            "После оплаты нажмите «Проверить оплату».",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Heleket topup error: {e}")
        await message.answer("Не удалось создать платёж. Попробуйте позже.")
        await state.clear()

@router.callback_query(F.data.startswith("check_topup_"))
async def check_topup_callback(call: CallbackQuery):
    await call.answer()
    payment_id = call.data.split("_")[2]
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT * FROM transactions WHERE payment_id = ?', (payment_id,)) as cursor:
            tx = await cursor.fetchone()
    if not tx:
        await call.message.answer("Транзакция не найдена.")
        return
    if tx[4] == "success":
        await call.message.answer("Этот платёж уже был обработан.")
        return
    if tx[3] == "yookassa":
        status = await check_yookassa_payment(payment_id)
        success_status = 'succeeded'
    else:
        status = await check_heleket_payment(payment_id)
        success_status = 'paid'
    if status == success_status:
        await db.update_balance(tx[1], tx[2])
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('UPDATE transactions SET status = ? WHERE id = ?', ("success", tx[0]))
            await conn.commit()
        await call.message.edit_text(f"✅ Баланс пополнен на {tx[2]:.2f} руб.", reply_markup=None)
        await call.message.answer("Теперь вы можете заказывать услуги.")
    else:
        await call.message.answer(f"❌ Платёж не прошел. Попробуйте позже.")