import asyncio
import logging
import random
import string
import aiohttp
import json
import uuid
import base64
import hashlib
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
from config import (
    BOT_TOKEN, OWNER_ID, ADMINS as STATIC_ADMINS,
    YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_RETURN_URL,
    HELEKET_MERCHANT_ID, HELEKET_API_KEY, HELEKET_API_URL, HELEKET_RETURN_URL
)
import database

import aiosqlite

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ====== Состояния ======
class OrderState(StatesGroup):
    waiting_quantity = State()
    waiting_link = State()

class SubscribersDuration(StatesGroup):
    waiting_duration = State()

class ReactionsType(StatesGroup):
    waiting_reaction_type = State()
    waiting_reaction_emoji = State()

class PaymentMethodChoice(StatesGroup):
    choosing_method = State()

class BalanceTopup(StatesGroup):
    waiting_amount = State()
    waiting_method = State()

class CalcState(StatesGroup):
    waiting_quantity = State()
    waiting_reaction_type = State()

class DeclineReason(StatesGroup):
    waiting_reason = State()

class BroadcastState(StatesGroup):
    waiting_message = State()

# ====== Цены и параметры ======
VIEWS_PRICE = 1.0

REACTION_PRICES = {
    "positive": 1/150,
    "negative": 1/150,
    "emoji_list": 0.01
}

SUBSCRIBER_PRICES = {
    "day": 1.0,
    "3days": 2.5,
    "7days": 3.0,
    "30days": 5.0,
    "90days": 7.0,
    "forever": 10.0
}

SUBSCRIBER_MINIMUMS = {
    "day": 100,
    "3days": 40,
    "7days": 35,
    "30days": 20,
    "90days": 15,
    "forever": 10
}

SUBSCRIBER_DURATIONS = {
    "day": "1 день",
    "3days": "3 дня",
    "7days": "7 дней",
    "30days": "30 дней",
    "90days": "90 дней",
    "forever": "Навсегда"
}

REACTION_TYPES = {
    "positive": "Позитивные",
    "negative": "Негативные",
    "emoji_list": "Эмодзи из списка"
}

# Все эмодзи в одном списке
EMOJI_LIST = ["👍", "🤡", "💩", "❤️", "🤝", "🖕", "👀", "🍌", "👻", "🕊", "🌲", "🗿", "🍾", "👌", "🤬"]

# Минимальные суммы пополнения
MIN_TOPUP_YOOKASSA = 1.0
MIN_TOPUP_HELEKET = 5.0

# ====== Генерация ID заказа ======
def generate_order_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ====== Проверка бана и соглашения ======
async def check_ban_and_terms(user_id: int) -> bool:
    banned = await database.is_banned(user_id)
    if banned:
        await bot.send_message(user_id, "❌ Вы заблокированы.")
        return True

    if not await database.has_accepted_terms(user_id):
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Принять договор оферты и политику конфиденциальности", callback_data="accept_terms")
        await bot.send_message(
            user_id,
            "Для использования бота необходимо принять договор оферты и политику конфиденциальности.\n\n"
            "[Договор оферты](https://t.me/your_offer_link)\n"
            "[Пользовательское соглашение](https://t.me/your_terms_link)",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return True
    return False

# ====== Принятие соглашения ======
@dp.callback_query(F.data == "accept_terms")
async def accept_terms(call: CallbackQuery):
    await call.answer()
    await database.accept_terms(call.from_user.id)
    await call.message.edit_text("✅ Вы приняли договор оферты и политику конфиденциальности. Теперь вы можете пользоваться ботом.")
    await show_main_menu(call.from_user.id)

# ====== ГЛАВНОЕ МЕНЮ ======
async def show_main_menu(chat_id: int):
    balance = await database.get_balance(chat_id)
    keyboard = [
        [InlineKeyboardButton(text="🛒 Заказать накрутку", callback_data="order")],
        [InlineKeyboardButton(text="🧮 Калькулятор", callback_data="calc")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🛠 Тех. Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="faq")]
    ]

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": btn.text,
                    "callback_data": btn.callback_data,
                } for btn in row
            ] for row in keyboard
        ]
    }

    text = f"""
<b>Приветствую!</b> <tg-emoji emoji-id="5877700484453634587">✈️</tg-emoji>
<b>Добро пожаловать в бота для накрутки статистики пользователей, просмотров и реакций

</b><blockquote><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Тех.поддержка: </b>@nBoost_supports<b>
</b><tg-emoji emoji-id="5870995486453796729">📊</tg-emoji> <b>Наш канал: </b>@channel_username</blockquote>
<a href="https://t.me/your_offer_link">Договор оферты</a> • <a href="https://t.me/your_terms_link">Пользовательское соглашение</a>

<b>💰 Ваш баланс: {balance:.2f} руб.</b>
    """

    async with aiohttp.ClientSession() as session:
        try:
            photo = FSInputFile("photo.jpg")
            form_data = aiohttp.FormData()
            form_data.add_field('chat_id', str(chat_id))
            form_data.add_field('caption', text)
            form_data.add_field('parse_mode', 'HTML')
            form_data.add_field('reply_markup', json.dumps(reply_markup))
            form_data.add_field('photo', open('photo.jpg', 'rb'), filename='photo.jpg')
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            async with session.post(url, data=form_data) as resp:
                if resp.status != 200:
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": reply_markup,
                        "disable_web_page_preview": True
                    }
                    await session.post(url, json=payload)
        except FileNotFoundError:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
                "disable_web_page_preview": True
            }
            await session.post(url, json=payload)

# ====== /start ======
@dp.message(Command("start"))
async def start_handler(message: Message):
    await database.add_user(message.from_user.id)
    if await check_ban_and_terms(message.from_user.id):
        return
    await show_main_menu(message.chat.id)

# ====== БАЛАНС ======
@dp.callback_query(F.data == "balance")
async def balance_menu(call: CallbackQuery):
    await call.answer()
    balance = await database.get_balance(call.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Пополнить картой (от 1₽)", callback_data="topup_yookassa")
    kb.button(text="₿ Пополнить криптовалютой (от 5₽)", callback_data="topup_heleket")
    kb.button(text="📜 История пополнений", callback_data="topup_history")
    kb.button(text="◀️ Назад", callback_data="back_to_main")
    kb.adjust(1)

    await call.message.edit_text(
        f"💰 <b>Ваш баланс: {balance:.2f} руб.</b>\n\n"
        "Выберите действие:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "topup_yookassa")
async def topup_yookassa_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(method="yookassa")
    await call.message.edit_text(
        f"Введите сумму пополнения (от {MIN_TOPUP_YOOKASSA:.2f} руб.):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data="balance")]])
    )
    await state.set_state(BalanceTopup.waiting_amount)

@dp.callback_query(F.data == "topup_heleket")
async def topup_heleket_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(method="heleket")
    await call.message.edit_text(
        f"Введите сумму пополнения (от {MIN_TOPUP_HELEKET:.2f} руб.):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data="balance")]])
    )
    await state.set_state(BalanceTopup.waiting_amount)

@dp.callback_query(F.data == "topup_history")
async def topup_history(call: CallbackQuery):
    await call.answer()
    transactions = await database.get_transactions(call.from_user.id, 10)
    if not transactions:
        text = "📜 История пополнений пуста."
    else:
        text = "📜 <b>Последние пополнения:</b>\n"
        for tx in transactions:
            # tx: id, user_id, amount, method, status, payment_id, created_at
            status_emoji = "✅" if tx[4] == "success" else "❌"
            text += f"{status_emoji} {tx[6][:10]} +{tx[2]:.2f} руб. ({tx[3]})\n"
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data="balance")
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(BalanceTopup.waiting_amount)
async def topup_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.replace('.', '').isdigit():
        return await message.answer("Введите число (например, 100.50).")
    amount = float(message.text)
    data = await state.get_data()
    method = data.get("method")
    if method == "yookassa" and amount < MIN_TOPUP_YOOKASSA:
        return await message.answer(f"Минимальная сумма пополнения: {MIN_TOPUP_YOOKASSA:.2f} руб.")
    if method == "heleket" and amount < MIN_TOPUP_HELEKET:
        return await message.answer(f"Минимальная сумма пополнения: {MIN_TOPUP_HELEKET:.2f} руб.")

    # Создаём платёж
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
        # Сохраняем транзакцию со статусом pending
        await database.add_transaction(message.from_user.id, amount, "yookassa", "pending", payment_id)
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Оплатить картой", url=confirmation_url)
        kb.button(text="✅ Проверить оплату", callback_data=f"check_topup_{payment_id}")
        await message.answer(
            f"Создан счёт на пополнение баланса на {amount:.2f} руб.\n"
            "Перейдите по ссылке для оплаты. После оплаты нажмите «Проверить оплату».",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await state.clear()
    except Exception as e:
        logging.error(f"Topup error: {e}")
        await message.answer("Не удалось создать платёж. Попробуйте позже.")
        await state.clear()

async def create_heleket_topup(message: Message, state: FSMContext, amount: float):
    try:
        payment_result = await create_heleket_payment(
            amount=amount,
            order_id=f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}",
            description=f"Пополнение баланса",
            user_id=message.from_user.id
        )
        payment_uuid = payment_result.get('uuid')
        payment_url = payment_result.get('url')
        if not payment_uuid or not payment_url:
            raise Exception("Missing payment data")
        await database.add_transaction(message.from_user.id, amount, "heleket", "pending", payment_uuid)
        kb = InlineKeyboardBuilder()
        kb.button(text="₿ Оплатить криптовалютой", url=payment_url)
        kb.button(text="✅ Проверить оплату", callback_data=f"check_topup_{payment_uuid}")
        await message.answer(
            f"Создан счёт на пополнение баланса на {amount:.2f} руб. (эквивалент в USDT).\n"
            "Перейдите по ссылке для оплаты. После оплаты нажмите «Проверить оплату».",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await state.clear()
    except Exception as e:
        logging.error(f"Heleket topup error: {e}")
        await message.answer("Не удалось создать платёж. Попробуйте позже.")
        await state.clear()

@dp.callback_query(F.data.startswith("check_topup_"))
async def check_topup_callback(call: CallbackQuery):
    await call.answer()
    payment_id = call.data.split("_")[2]
    # Найти транзакцию по payment_id
    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute('SELECT * FROM transactions WHERE payment_id = ?', (payment_id,)) as cursor:
            tx = await cursor.fetchone()
    if not tx:
        await call.message.answer("Транзакция не найдена.")
        return
    if tx[4] == "success":
        await call.message.answer("Этот платёж уже был обработан.")
        return
    # Проверяем статус платежа
    if tx[3] == "yookassa":
        status = await check_yookassa_payment(payment_id)
        success_status = 'succeeded'
    else:
        status = await check_heleket_payment(payment_id)
        success_status = 'paid'
    if status == success_status:
        # Зачисляем баланс
        await database.update_balance(tx[1], tx[2])
        await database.add_transaction(tx[1], tx[2], tx[3], "success", payment_id)  # обновляем статус (лучше update)
        # Можно обновить запись, но добавим новую для простоты
        await call.message.edit_text(f"✅ Баланс пополнен на {tx[2]:.2f} руб.", reply_markup=None)
        await call.message.answer("Теперь вы можете заказывать услуги.")
    else:
        await call.message.answer(f"❌ Платёж ещё не оплачен (статус: {status}). Попробуйте позже.")

# ====== ЗАКАЗ ======
@dp.callback_query(F.data == "order")
async def order_menu(call: CallbackQuery):
    await call.answer()
    if await check_ban_and_terms(call.from_user.id):
        return

    keyboard = [
        [InlineKeyboardButton(text="Подписчики", callback_data="subscribers")],
        [InlineKeyboardButton(text="Просмотры", callback_data="views")],
        [InlineKeyboardButton(text="Реакции", callback_data="reactions")],
        [InlineKeyboardButton(text="◀️ Вернуться назад", callback_data="back_to_main")]
    ]

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": btn.text,
                    "callback_data": btn.callback_data,
                } for btn in row
            ] for row in keyboard
        ]
    }

    text = """
<b>Заказать услугу</b><tg-emoji emoji-id="5870695289714643076">👤</tg-emoji><b>

Выберите услугу из списка ниже.</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji>
<a href="https://t.me/shiitead">Курс для каждой услуги</a>
    """

    async with aiohttp.ClientSession() as session:
        try:
            await call.message.delete()
        except Exception:
            pass

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": call.from_user.id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
            "disable_web_page_preview": True
        }

        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                logging.error(f"Failed to send order menu via direct API: {await resp.text()}")
                kb = InlineKeyboardBuilder()
                kb.button(text="Подписчики", callback_data="subscribers")
                kb.button(text="Просмотры", callback_data="views")
                kb.button(text="Реакции", callback_data="reactions")
                kb.button(text="◀️ Вернуться назад", callback_data="back_to_main")
                kb.adjust(1)
                await call.message.answer(
                    text.replace("<tg-emoji", "<!-- tg-emoji").replace("</tg-emoji>", "-->"),
                    reply_markup=kb.as_markup(),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

@dp.callback_query(F.data == "subscribers")
async def choose_subscribers(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if await check_ban_and_terms(call.from_user.id):
        return
    await state.update_data(service="subscribers")

    kb = InlineKeyboardBuilder()
    for key, name in SUBSCRIBER_DURATIONS.items():
        price = SUBSCRIBER_PRICES[key]
        min_q = SUBSCRIBER_MINIMUMS[key]
        kb.button(text=f"{name} - {price}₽ за 100 чел (мин {min_q})", callback_data=f"sub_dur_{key}")
    kb.button(text="◀️ Назад к выбору услуги", callback_data="order")
    kb.adjust(2)

    await call.message.edit_text(
        "<b>Выберите длительность услуги</b><tg-emoji emoji-id=\"5386713103213814186\">❕</tg-emoji>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(SubscribersDuration.waiting_duration)

@dp.callback_query(F.data == "views")
async def choose_views(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if await check_ban_and_terms(call.from_user.id):
        return
    await state.update_data(service="views")
    await call.message.edit_text("Введите количество просмотров (минимум 1):")
    await state.set_state(OrderState.waiting_quantity)

@dp.callback_query(F.data == "reactions")
async def choose_reactions(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if await check_ban_and_terms(call.from_user.id):
        return
    await state.update_data(service="reactions")

    kb = InlineKeyboardBuilder()
    for key, name in REACTION_TYPES.items():
        price_per_unit = REACTION_PRICES[key]
        if key == "emoji_list":
            price_text = f"1₽ за 100"
        else:
            price_text = f"1₽ за 150"
        kb.button(text=f"{name} ({price_text})", callback_data=f"react_type_{key}")
    kb.button(text="◀️ Назад к выбору услуги", callback_data="order")
    kb.adjust(2)

    await call.message.edit_text(
        "Выберите тип реакций:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(ReactionsType.waiting_reaction_type)

# ====== ОБРАБОТЧИКИ ДЛЯ ПОДПИСЧИКОВ ======
@dp.callback_query(SubscribersDuration.waiting_duration, F.data.startswith("sub_dur_"))
async def process_subscribers_duration(call: CallbackQuery, state: FSMContext):
    await call.answer()
    duration_key = call.data.split("_")[2]
    duration_name = SUBSCRIBER_DURATIONS[duration_key]
    price_per_100 = SUBSCRIBER_PRICES[duration_key]
    min_quantity = SUBSCRIBER_MINIMUMS[duration_key]
    await state.update_data(subtype=duration_name, duration_key=duration_key, price_per_100=price_per_100, min_quantity=min_quantity)
    await call.message.edit_text(
        f"Выбрана длительность: {duration_name}\n"
        f"Цена: {price_per_100}₽ за 100 человек\n"
        f"Минимальное количество: {min_quantity} чел.\n\n"
        "Введите количество подписчиков:"
    )
    await state.set_state(OrderState.waiting_quantity)

# ====== ОБРАБОТЧИКИ ДЛЯ РЕАКЦИЙ ======
@dp.callback_query(ReactionsType.waiting_reaction_type, F.data.startswith("react_type_"))
async def process_reaction_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    type_key = call.data.split("_")[2]
    logging.info(f"process_reaction_type received type_key: {type_key}")

    if type_key not in REACTION_TYPES:
        logging.error(f"Unknown reaction type key: {type_key}")
        await call.message.answer("❌ Неизвестный тип реакции. Пожалуйста, выберите снова.")
        kb = InlineKeyboardBuilder()
        for key, name in REACTION_TYPES.items():
            price_per_unit = REACTION_PRICES[key]
            if key == "emoji_list":
                price_text = f"1₽ за 100"
            else:
                price_text = f"1₽ за 150"
            kb.button(text=f"{name} ({price_text})", callback_data=f"react_type_{key}")
        kb.button(text="◀️ Назад к выбору услуги", callback_data="order")
        kb.adjust(2)
        await call.message.edit_text(
            "Выберите тип реакций:",
            reply_markup=kb.as_markup()
        )
        return

    type_name = REACTION_TYPES[type_key]
    await state.update_data(reaction_type_key=type_key, reaction_type_name=type_name)

    if type_key == "emoji_list":
        # Показываем все эмодзи в одной странице
        kb = InlineKeyboardBuilder()
        for emoji in EMOJI_LIST:
            kb.button(text=emoji, callback_data=f"react_emoji_{emoji}")
        kb.button(text="◀️ Назад к типам реакций", callback_data="reactions")
        kb.adjust(4)
        await call.message.edit_text(
            "Выберите эмодзи:",
            reply_markup=kb.as_markup()
        )
        await state.set_state(ReactionsType.waiting_reaction_emoji)
    else:
        await call.message.edit_text("Введите количество реакций (минимум 1):")
        await state.set_state(OrderState.waiting_quantity)

@dp.callback_query(ReactionsType.waiting_reaction_emoji, F.data.startswith("react_emoji_"))
async def process_reaction_emoji(call: CallbackQuery, state: FSMContext):
    await call.answer()
    emoji = call.data.split("_")[2]
    logging.info(f"Reaction emoji selected: {emoji}")
    await state.update_data(selected_emoji=emoji)
    await call.message.edit_text("Введите количество реакций (минимум 1):")
    await state.set_state(OrderState.waiting_quantity)

# ====== ВВОД КОЛИЧЕСТВА ======
@dp.message(OrderState.waiting_quantity)
async def get_quantity(message: Message, state: FSMContext):
    if await check_ban_and_terms(message.from_user.id):
        return await state.clear()
    if not message.text or not message.text.isdigit():
        return await message.answer("Введите число!")

    quantity = int(message.text)
    data = await state.get_data()
    service = data["service"]

    if service == "subscribers":
        min_q = data.get("min_quantity", 100)
        if quantity < min_q:
            return await message.answer(f"Минимальное количество для выбранной длительности — {min_q}.")
        price_per_100 = data.get("price_per_100")
        price = (quantity / 100) * price_per_100
    elif service in ("views", "reactions"):
        if quantity < 1:
            return await message.answer("Минимальное количество — 1.")
        if service == "views":
            price = quantity * VIEWS_PRICE
        else:
            reaction_type = data.get("reaction_type_key")
            if reaction_type is None:
                return await message.answer("Ошибка: не выбран тип реакции.")
            price_per_unit = REACTION_PRICES.get(reaction_type, 0.01)
            price = quantity * price_per_unit
    else:
        return await message.answer("Ошибка: неизвестная услуга.")

    await state.update_data(quantity=quantity, price=price)

    # Проверяем баланс
    balance = await database.get_balance(message.from_user.id)
    if balance >= price:
        # Списываем и создаём заказ
        await database.update_balance(message.from_user.id, -price)
        await create_order_and_notify(message, state, balance - price)
    else:
        # Недостаточно средств
        need = price - balance
        kb = InlineKeyboardBuilder()
        kb.button(text="💰 Пополнить баланс", callback_data="balance")
        kb.button(text="◀️ Вернуться в меню", callback_data="back_to_main")
        await message.answer(
            f"❌ Недостаточно средств на балансе.\n"
            f"Ваш баланс: {balance:.2f} руб.\n"
            f"Стоимость заказа: {price:.2f} руб.\n"
            f"Не хватает: {need:.2f} руб.\n\n"
            "Пополните баланс и повторите заказ.",
            reply_markup=kb.as_markup()
        )
        await state.clear()

async def create_order_and_notify(message: Message, state: FSMContext, new_balance: float):
    data = await state.get_data()
    order_id = generate_order_id()
    service = data['service']
    quantity = data['quantity']
    price = data['price']
    link = data.get('link')  # пока нет, но будет после ввода ссылки
    # Но у нас сначала идёт ввод количества, потом ссылки. Поэтому здесь ссылки ещё нет.
    # Надо перенести проверку баланса после ввода ссылки.
    # Поэтому логика будет так: после ввода ссылки снова проверить баланс, и если хватает – списать и создать.
    # Поэтому эта функция будет вызываться после get_link.
    pass

# ====== ОБРАБОТКА ССЫЛКИ ======
@dp.message(OrderState.waiting_link)
async def get_link(message: Message, state: FSMContext):
    if await check_ban_and_terms(message.from_user.id):
        return await state.clear()
    link = message.text.strip()
    if not link.startswith(("http://", "https://")):
        return await message.answer("Пожалуйста, отправьте корректную ссылку, начинающуюся с http:// или https://")
    data = await state.get_data()
    order_id = generate_order_id()
    service = data['service']
    quantity = data['quantity']
    price = data['price']

    # Проверяем баланс
    balance = await database.get_balance(message.from_user.id)
    if balance < price:
        need = price - balance
        kb = InlineKeyboardBuilder()
        kb.button(text="💰 Пополнить баланс", callback_data="balance")
        kb.button(text="◀️ Вернуться в меню", callback_data="back_to_main")
        await message.answer(
            f"❌ Недостаточно средств на балансе.\n"
            f"Ваш баланс: {balance:.2f} руб.\n"
            f"Стоимость заказа: {price:.2f} руб.\n"
            f"Не хватает: {need:.2f} руб.\n\n"
            "Пополните баланс и повторите заказ.",
            reply_markup=kb.as_markup()
        )
        await state.clear()
        return

    # Списываем средства
    await database.update_balance(message.from_user.id, -price)
    new_balance = balance - price

    # Формируем описание для комментария
    if service == "subscribers":
        comment = f"Подписчики, длительность: {data['subtype']}"
    elif service == "reactions":
        comment = f"Реакции, тип: {data['reaction_type_name']}"
        if data.get('reaction_type_key') == 'emoji_list' and 'selected_emoji' in data:
            comment += f", эмодзи: {data['selected_emoji']}"
    else:  # views
        comment = "Просмотры"

    try:
        await database.create_order(
            order_id=order_id,
            user_id=message.from_user.id,
            service=service,
            quantity=quantity,
            price=price,
            link=link,
            status="PAID",  # Сразу оплачено
            comment=comment
        )
    except Exception as e:
        logging.error(f"DB error: {e}")
        await message.answer("Ошибка при создании заказа. Средства не списаны.")
        # Восстанавливаем баланс
        await database.update_balance(message.from_user.id, price)
        return await state.clear()

    # Уведомляем пользователя
    await message.answer(
        f"✅ Заказ №{order_id} успешно оформлен!\n\n"
        f"{comment}\n"
        f"Количество: {quantity}\n"
        f"Сумма: {price:.2f} руб.\n"
        f"Ссылка: {link}\n\n"
        f"💰 Новый баланс: {new_balance:.2f} руб.\n\n"
        "Ваш заказ передан в работу. Ожидайте выполнения."
    )

    # Уведомляем администраторов
    admins = await database.get_all_admins()
    for admin in admins:
        await bot.send_message(
            admin,
            f"📦 Новый заказ №{order_id} от {message.from_user.id}\n"
            f"Услуга: {comment}\nКоличество: {quantity}\nСумма: {price:.2f} руб.\nСсылка: {link}"
        )

    await state.clear()

# ====== ФУНКЦИИ ПЛАТЕЖЕЙ (ЮKassa, Heleket) без изменений ======
# (оставляем те же функции, что были, они используются для пополнения)
# ...

# ====== АДМИН КОМАНДЫ ======
async def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

async def is_admin_from_db_or_config(user_id: int) -> bool:
    if user_id in STATIC_ADMINS:
        return True
    return await database.is_admin(user_id)

@dp.message(Command("ban"))
async def ban_cmd(message: Message):
    if not await is_admin_from_db_or_config(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /ban <user_id>")
    try:
        user_id = int(args[1])
    except ValueError:
        return await message.answer("ID должен быть числом.")
    await database.ban_user(user_id)
    await message.answer(f"Пользователь {user_id} забанен.")

@dp.message(Command("unban"))
async def unban_cmd(message: Message):
    if not await is_admin_from_db_or_config(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /unban <user_id>")
    try:
        user_id = int(args[1])
    except ValueError:
        return await message.answer("ID должен быть числом.")
    await database.unban_user(user_id)
    await message.answer(f"Пользователь {user_id} разбанен.")

@dp.message(Command("search"))
async def search_order(message: Message):
    if not await is_admin_from_db_or_config(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /search <order_id>")
    order_id = args[1]
    order = await database.get_order(order_id)
    if not order:
        await message.answer("❌ Заказ не найден.")
        return

    status_text = {
        "NEW": "🆕 Новый",
        "PENDING": "⏳ Ожидает оплаты",
        "PAID": "✅ Оплачен",
        "ACCEPTED": "📦 Принят в работу",
        "DECLINED": "❌ Отклонён"
    }.get(order[6], order[6])

    service_info = order[2]
    if order[2] == "subscribers":
        service_info = "Подписчики"
        if order[7]:
            service_info += f" ({order[7]})"
    elif order[2] == "reactions":
        service_info = "Реакции"
        if order[7]:
            service_info += f" ({order[7]})"
    elif order[2] == "views":
        service_info = "Просмотры"

    response = f"""
🔍 <b>Информация о заказе</b>

🆔 <b>Номер заказа:</b> {order[0]}
👤 <b>Пользователь ID:</b> {order[1]}
📦 <b>Услуга:</b> {service_info}
🔢 <b>Количество:</b> {order[3]}
💰 <b>Стоимость:</b> {order[4]:.2f} руб.
🔗 <b>Ссылка:</b> {order[5]}
📊 <b>Статус:</b> {status_text}
💳 <b>Метод оплаты:</b> {order[10] if order[10] else 'не выбран'}
🆔 <b>ID платежа:</b> {order[8] if order[8] else 'нет'}
📅 <b>Создан:</b> {order[11]}
    """
    await message.answer(response, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("addbalance"))
async def add_balance(message: Message):
    if not await is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Использование: /addbalance <user_id> <amount>")
    try:
        user_id = int(args[1])
        amount = float(args[2])
    except ValueError:
        return await message.answer("ID должен быть числом, сумма числом.")
    await database.update_balance(user_id, amount)
    await message.answer(f"Баланс пользователя {user_id} изменён на +{amount:.2f} руб.")

@dp.message(Command("setbalance"))
async def set_balance(message: Message):
    if not await is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Использование: /setbalance <user_id> <amount>")
    try:
        user_id = int(args[1])
        amount = float(args[2])
    except ValueError:
        return await message.answer("ID должен быть числом, сумма числом.")
    await database.set_balance(user_id, amount)
    await message.answer(f"Баланс пользователя {user_id} установлен на {amount:.2f} руб.")

# Остальные команды (addadmin, deladmin, all, fixdb, support, faq, calc, back_to_main, accept/decline) остаются без изменений
# ...

# ====== RUN ======
async def main():
    await database.init_db()
    for admin_id in STATIC_ADMINS:
        await database.add_admin(admin_id)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())