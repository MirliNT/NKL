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

class CalcState(StatesGroup):
    waiting_quantity = State()

class DeclineReason(StatesGroup):
    waiting_reason = State()

class BroadcastState(StatesGroup):
    waiting_message = State()

class PaymentState(StatesGroup):
    waiting_for_payment = State()

# ====== Цены и параметры ======
PRICES = {
    "views": 1.0,
    "reactions": 1.0
}

SUBSCRIBER_PRICES = {
    "day": 1.0,
    "3days": 2.5,
    "7days": 3.0,
    "30days": 5.0,
    "90days": 7.0,
    "forever": 10.0
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
    "custom": "Кастомные",
    "positive": "Позитивные",
    "negative": "Негативные",
    "emoji_list": "Эмодзи из списка"
}

EMOJI_LIST = ["❤️", "⚡", "👍", "💩", "🖕", "👨‍💻"]

def generate_order_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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

@dp.callback_query(F.data == "accept_terms")
async def accept_terms(call: CallbackQuery):
    await call.answer()
    await database.accept_terms(call.from_user.id)
    await call.message.edit_text("✅ Вы приняли договор оферты и политику конфиденциальности. Теперь вы можете пользоваться ботом.")
    await show_main_menu(call.from_user.id)

async def show_main_menu(chat_id: int):
    keyboard = [
        [InlineKeyboardButton(text="🛒 Заказать накрутку", callback_data="order")],
        [InlineKeyboardButton(text="🧮 Калькулятор", callback_data="calc")],
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
    text = """
<b>Приветствую!</b> ✈️
<b>Добро пожаловать в бота для накрутки статистики пользователей, просмотров и реакций

</b><blockquote>👤 <b>Тех.поддержка: @support_username
</b>📈 <b>Наш канал: @channel_username</b></blockquote>

<a href="https://t.me/your_offer_link">Договор оферты</a> • <a href="https://t.me/your_terms_link">Пользовательское соглашение</a>
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

@dp.message(Command("start"))
async def start_handler(message: Message):
    await database.add_user(message.from_user.id)
    if await check_ban_and_terms(message.from_user.id):
        return
    await show_main_menu(message.chat.id)

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
        kb.button(text=f"{name} - {price}₽ за 100 чел", callback_data=f"sub_dur_{key}")
    kb.button(text="◀️ Назад к выбору услуги", callback_data="order")
    kb.adjust(2)
    await call.message.edit_text(
        "Выберите длительность подписки (минимальный заказ — 100 человек):",
        reply_markup=kb.as_markup()
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
        kb.button(text=name, callback_data=f"react_type_{key}")
    kb.button(text="◀️ Назад к выбору услуги", callback_data="order")
    kb.adjust(2)
    await call.message.edit_text(
        "Выберите тип реакций:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(ReactionsType.waiting_reaction_type)

@dp.callback_query(SubscribersDuration.waiting_duration, F.data.startswith("sub_dur_"))
async def process_subscribers_duration(call: CallbackQuery, state: FSMContext):
    await call.answer()
    duration_key = call.data.split("_")[2]
    duration_name = SUBSCRIBER_DURATIONS[duration_key]
    price_per_100 = SUBSCRIBER_PRICES[duration_key]
    await state.update_data(subtype=duration_name, duration_key=duration_key, price_per_100=price_per_100)
    await call.message.edit_text(
        f"Выбрана длительность: {duration_name}\n"
        f"Цена: {price_per_100}₽ за 100 человек\n\n"
        "Введите количество подписчиков (минимум 100, кратно 100):"
    )
    await state.set_state(OrderState.waiting_quantity)

@dp.callback_query(ReactionsType.waiting_reaction_type, F.data.startswith("react_type_"))
async def process_reaction_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    type_key = call.data.split("_")[2]
    logging.info(f"process_reaction_type received type_key: {type_key}")
    if type_key == "emoji":
        type_key = "emoji_list"
        logging.info("Converted old key 'emoji' to 'emoji_list'")
    if type_key not in REACTION_TYPES:
        logging.error(f"Unknown reaction type key: {type_key}")
        await call.message.answer("❌ Неизвестный тип реакции. Пожалуйста, выберите снова.")
        kb = InlineKeyboardBuilder()
        for key, name in REACTION_TYPES.items():
            kb.button(text=name, callback_data=f"react_type_{key}")
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
        kb = InlineKeyboardBuilder()
        for emoji in EMOJI_LIST:
            kb.button(text=emoji, callback_data=f"react_emoji_{emoji}")
        kb.button(text="◀️ Назад к типам реакций", callback_data="reactions")
        kb.adjust(3)
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
        if quantity < 100:
            return await message.answer("Минимальное количество подписчиков — 100.")
        if quantity % 100 != 0:
            return await message.answer("Количество подписчиков должно быть кратно 100.")
        price_per_100 = data.get("price_per_100")
        price = (quantity / 100) * price_per_100
    elif service in ("views", "reactions"):
        if quantity < 1:
            return await message.answer("Минимальное количество — 1.")
        price = quantity * PRICES[service]
    else:
        return await message.answer("Ошибка: неизвестная услуга.")
    await state.update_data(quantity=quantity, price=price)
    await message.answer(f"💰 Стоимость: {price:.2f} руб.\n\nОтправьте ссылку:")
    await state.set_state(OrderState.waiting_link)

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

    if service == "subscribers":
        description = f"Подписчики, длительность: {data['subtype']}, кол-во: {quantity}"
    elif service == "reactions":
        base = f"Реакции, тип: {data['reaction_type_name']}"
        if data.get('reaction_type_key') == 'emoji_list' and 'selected_emoji' in data:
            base += f", эмодзи: {data['selected_emoji']}"
        description = f"{base}, кол-во: {quantity}"
    else:  # views
        description = f"Просмотры, кол-во: {quantity}"

    try:
        await database.create_order(
            order_id=order_id,
            user_id=message.from_user.id,
            service=service,
            quantity=quantity,
            price=price,
            link=link,
            status="PENDING"
        )
    except Exception as e:
        logging.error(f"DB error: {e}")
        await message.answer("Ошибка при создании заказа. Попробуйте позже.")
        return await state.clear()

    await state.update_data(order_id=order_id, description=description)

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Банковская карта (ЮKassa)", callback_data="pay_yookassa")
    kb.button(text="₿ Криптовалюта (Heleket)", callback_data="pay_heleket")
    kb.button(text="◀️ Вернуться в главное меню", callback_data="back_to_main")
    kb.adjust(1)

    await message.answer(
        f"✅ Заказ предварительно сохранён.\n{description}\nСумма: {price:.2f} руб.\n\nТеперь выберите способ оплаты:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(PaymentMethodChoice.choosing_method)

# ====== ЮKassa ======
async def create_yookassa_payment(amount: float, description: str, order_id: str, user_id: int):
    auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4())
    }
    data = {
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": YOOKASSA_RETURN_URL
        },
        "capture": True,
        "description": description,
        "metadata": {
            "order_id": order_id,
            "user_id": user_id
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.yookassa.ru/v3/payments", headers=headers, json=data) as resp:
            response_text = await resp.text()
            logging.info(f"YooKassa response status: {resp.status}")
            logging.info(f"YooKassa response body: {response_text}")
            if resp.status not in (200, 201):
                raise Exception(f"YooKassa error {resp.status}: {response_text}")
            return json.loads(response_text)

@dp.callback_query(F.data == "pay_yookassa")
async def pay_with_yookassa(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    order_id = data.get('order_id')
    if not order_id:
        await call.message.answer("Ошибка: заказ не найден. Начните заново.")
        await state.clear()
        return
    order = await database.get_order(order_id)
    if not order:
        await call.message.answer("Ошибка: заказ не найден в базе.")
        await state.clear()
        return
    price = order[4]
    description = data.get('description', f"Заказ {order_id}")
    user_id = call.from_user.id
    try:
        payment_data = await create_yookassa_payment(
            amount=price,
            description=description,
            order_id=order_id,
            user_id=user_id
        )
        payment_id = payment_data.get('id')
        confirmation_url = payment_data.get('confirmation', {}).get('confirmation_url')
        if not payment_id or not confirmation_url:
            raise Exception("Missing payment_id or confirmation_url in YooKassa response")
        await database.update_order_payment_id(order_id, payment_id)
        await database.update_order_payment_method(order_id, "yookassa")
        logging.info(f"Order {order_id} updated with payment_id={payment_id}, method=yookassa")
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Оплатить картой", url=confirmation_url)
        kb.adjust(1)
        await call.message.edit_text(
            f"✅ Заказ №{order_id} готов к оплате через ЮKassa!\n\n"
            f"{description}\nСумма: {price:.2f} руб.\n\n"
            f"Для оплаты перейдите по ссылке ниже. После успешной оплаты заказ будет подтверждён автоматически.",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await state.set_state(PaymentState.waiting_for_payment)
    except Exception as e:
        logging.error(f"YooKassa error: {e}")
        await call.message.answer("Не удалось создать платёж. Попробуйте позже.")
        await state.clear()

# ====== Heleket ======
async def create_heleket_payment(amount: float, order_id: str, description: str, user_id: int):
    payload = {
        "amount": f"{amount:.2f}",
        "currency": "USDT",
        "order_id": order_id,
    }
    sorted_payload = {k: payload[k] for k in sorted(payload.keys())}
    json_data = json.dumps(sorted_payload, separators=(',', ':'))
    logging.info(f"Heleket request body: {json_data}")
    base64_data = base64.b64encode(json_data.encode()).decode()
    api_key = HELEKET_API_KEY.strip()
    merchant_id = HELEKET_MERCHANT_ID.strip()
    sign = hashlib.md5((base64_data + api_key).encode()).hexdigest()
    logging.info(f"Heleket sign: {sign}")
    headers = {
        "merchant": merchant_id,
        "sign": sign,
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{HELEKET_API_URL}/payment", headers=headers, data=json_data) as resp:
            response_text = await resp.text()
            logging.info(f"Heleket response status: {resp.status}")
            logging.info(f"Heleket response body: {response_text}")
            if resp.status != 200:
                raise Exception(f"Heleket HTTP error {resp.status}: {response_text}")
            response_json = json.loads(response_text)
            if response_json.get('state') != 0:
                raise Exception(f"Heleket error: {response_json}")
            return response_json['result']

async def check_heleket_payment(payment_uuid: str):
    payload = {"uuid": payment_uuid}
    json_data = json.dumps(payload, separators=(',', ':'))
    base64_data = base64.b64encode(json_data.encode()).decode()
    api_key = HELEKET_API_KEY.strip()
    merchant_id = HELEKET_MERCHANT_ID.strip()
    sign = hashlib.md5((base64_data + api_key).encode()).hexdigest()
    headers = {
        "merchant": merchant_id,
        "sign": sign,
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{HELEKET_API_URL}/payment/info", headers=headers, data=json_data) as resp:
            if resp.status != 200:
                logging.error(f"Heleket payment info error: HTTP {resp.status}")
                return None
            response_json = await resp.json()
            if response_json.get('state') != 0:
                logging.error(f"Heleket payment info error: {response_json}")
                return None
            return response_json['result'].get('payment_status')

@dp.callback_query(F.data == "pay_heleket")
async def pay_with_heleket(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    order_id = data.get('order_id')
    if not order_id:
        await call.message.answer("Ошибка: заказ не найден. Начните заново.")
        await state.clear()
        return
    order = await database.get_order(order_id)
    if not order:
        await call.message.answer("Ошибка: заказ не найден в базе.")
        await state.clear()
        return
    price = order[4]
    description = data.get('description', f"Заказ {order_id}")
    user_id = call.from_user.id
    try:
        payment_result = await create_heleket_payment(
            amount=price,
            order_id=order_id,
            description=description,
            user_id=user_id
        )
        payment_uuid = payment_result.get('uuid')
        payment_url = payment_result.get('url')
        if not payment_uuid or not payment_url:
            raise Exception("Missing uuid or url in Heleket response")
        await database.update_order_payment_id(order_id, payment_uuid)
        await database.update_order_payment_method(order_id, "heleket")
        logging.info(f"Order {order_id} updated with payment_uuid={payment_uuid}, method=heleket")
        kb = InlineKeyboardBuilder()
        kb.button(text="₿ Оплатить криптовалютой", url=payment_url)
        kb.adjust(1)
        await call.message.edit_text(
            f"✅ Заказ №{order_id} готов к оплате через Heleket!\n\n"
            f"{description}\nСумма: {price:.2f} руб. (эквивалент {price:.2f} USDT)\n\n"
            f"Для оплаты перейдите по ссылке ниже. После успешной оплаты заказ будет подтверждён автоматически.",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await state.set_state(PaymentState.waiting_for_payment)
    except Exception as e:
        logging.error(f"Heleket error: {e}")
        await call.message.answer("Не удалось создать платёж через Heleket. Попробуйте позже.")
        await state.clear()

# ====== Проверка статусов ======
async def check_yookassa_payment(payment_id: str):
    auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.yookassa.ru/v3/payments/{payment_id}", headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get('status')

async def check_payments_status():
    while True:
        try:
            pending_orders = await database.get_pending_orders()
            if pending_orders:
                logging.info(f"Checking {len(pending_orders)} pending orders...")
            for order in pending_orders:
                order_id = order[0]
                payment_id = order[8]
                payment_method = order[10] if len(order) > 10 else None
                if not payment_id:
                    logging.warning(f"Order {order_id} has no payment_id, skipping.")
                    continue
                if not payment_method:
                    logging.warning(f"Order {order_id} has payment_id but no payment_method, skipping.")
                    continue
                logging.info(f"Checking order {order_id}, payment_method: {payment_method}, payment_id: {payment_id}")
                try:
                    if payment_method == 'yookassa':
                        status = await check_yookassa_payment(payment_id)
                    elif payment_method == 'heleket':
                        status = await check_heleket_payment(payment_id)
                    else:
                        logging.warning(f"Unknown payment method {payment_method} for order {order_id}")
                        continue
                    if status is None:
                        logging.warning(f"Payment {payment_id} not found or error")
                        continue
                    logging.info(f"Payment {payment_id} status: {status}")
                    if status in ('succeeded', 'paid'):
                        await database.update_order_status(order_id, "PAID", f"Оплачено через {payment_method} (авто)")
                        user_id = order[1]
                        try:
                            await bot.send_message(
                                user_id,
                                f"✅ Ваш заказ №{order_id} оплачен! Мы начали выполнение.",
                                disable_web_page_preview=True
                            )
                            logging.info(f"User {user_id} notified about payment for order {order_id}")
                        except Exception as e:
                            logging.error(f"Failed to notify user {user_id}: {e}")
                        admins = await database.get_all_admins()
                        for admin in admins:
                            try:
                                await bot.send_message(
                                    admin,
                                    f"💰 Автоматически подтверждена оплата заказа №{order_id} от пользователя {user_id} через {payment_method}."
                                )
                            except Exception as e:
                                logging.error(f"Failed to notify admin {admin}: {e}")
                        logging.info(f"Order {order_id} marked as PAID via polling")
                except Exception as e:
                    logging.error(f"Error checking payment {payment_id} for order {order_id}: {e}")
        except Exception as e:
            logging.error(f"Error in payment status checker: {e}")
        await asyncio.sleep(30)

# ====== Админ-команды ======
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
    if order:
        await message.answer(str(order))
    else:
        await message.answer("Заказ не найден.")

@dp.message(Command("addadmin"))
async def add_admin(message: Message):
    if not await is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /addadmin <user_id>")
    try:
        user_id = int(args[1])
    except ValueError:
        return await message.answer("ID должен быть числом.")
    await database.add_admin(user_id)
    await message.answer(f"Пользователь {user_id} добавлен в администраторы.")

@dp.message(Command("deladmin"))
async def remove_admin(message: Message):
    if not await is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /deladmin <user_id>")
    try:
        user_id = int(args[1])
    except ValueError:
        return await message.answer("ID должен быть числом.")
    await database.remove_admin(user_id)
    await message.answer(f"Пользователь {user_id} удалён из администраторов.")

@dp.message(Command("all"))
async def broadcast_command(message: Message, state: FSMContext):
    if not await is_owner(message.from_user.id):
        return
    await message.answer("Отправьте сообщение для рассылки всем пользователям (можно с медиа).")
    await state.set_state(BroadcastState.waiting_message)

@dp.message(BroadcastState.waiting_message)
async def broadcast_message(message: Message, state: FSMContext):
    if not await is_owner(message.from_user.id):
        return await state.clear()
    users = await database.get_all_users()
    await message.answer(f"Начинаю рассылку {len(users)} пользователям...")
    sent = 0
    blocked = 0
    for user_id in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                disable_web_page_preview=True
            )
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            blocked += 1
        except Exception as e:
            logging.error(f"Failed to send to {user_id}: {e}")
    await message.answer(f"Рассылка завершена.\nОтправлено: {sent}\nЗаблокировали бота: {blocked}")
    await state.clear()

# ====== Остальные хендлеры (поддержка, faq, назад, калькулятор, fixdb, accept/decline) ======
# (Здесь разместите все остальные хендлеры из предыдущего кода, они остаются без изменений)
# Для краткости я их не копирую, но в реальном файле они должны быть.

# ====== RUN ======
async def main():
    await database.init_db()
    for admin_id in STATIC_ADMINS:
        await database.add_admin(admin_id)
    asyncio.create_task(check_payments_status())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())