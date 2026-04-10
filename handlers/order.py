import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_instance import bot
from states.states import OrderState
import database as db
from keyboards import get_platform_keyboard, get_telegram_menu, get_vk_menu, get_instagram_menu, get_tiktok_menu, get_stars_menu
from utils.helpers import generate_order_id, validate_link
from utils.vexboost import create_order as create_vexboost_order, VexBoostError
import settings

router = Router()
logger = logging.getLogger(__name__)

# ====== Меню выбора платформы ======
@router.callback_query(F.data == "order")
async def order_menu(call: CallbackQuery):
    await call.answer()
    kb = get_platform_keyboard()
    text = "<b>Выберите платформу для накрутки</b>"
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ====== Telegram ======
@router.callback_query(F.data == "platform_telegram")
async def telegram_menu(call: CallbackQuery):
    await call.answer()
    kb = get_telegram_menu()
    text = "<b>Выберите услугу для Telegram</b>"
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ----- Просмотры -----
@router.callback_query(F.data == "tg_views")
async def tg_views(call: CallbackQuery, state: FSMContext):
    await call.answer()
    service = await db.get_services_by_subcategory("telegram", "views", None)
    if not service:
        await call.message.answer("Услуга временно недоступна.")
        return
    await state.update_data(service_id=service[0][0], service_name="Просмотры Telegram")
    await call.message.answer("Введите количество просмотров (минимум 1):")
    await state.set_state(OrderState.waiting_quantity)

# ----- Подписчики -----
@router.callback_query(F.data == "tg_subscribers")
async def tg_subscribers_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(service_name="Подписчики Telegram", platform="telegram", category="subscribers")
    kb = InlineKeyboardBuilder()
    durations = [
        ("1 день", "day"),
        ("3 дня", "3days"),
        ("7 дней", "7days"),
        ("30 дней", "30days"),
        ("Навсегда", "forever")
    ]
    for name, key in durations:
        kb.button(text=name, callback_data=f"tg_sub_{key}")
    kb.button(text="◀️ Назад", callback_data="platform_telegram")
    kb.adjust(2)
    await call.message.edit_text("Выберите длительность подписки:", reply_markup=kb.as_markup())
    await state.set_state(OrderState.waiting_quantity)

@router.callback_query(F.data.startswith("tg_sub_"))
async def tg_sub_duration(call: CallbackQuery, state: FSMContext):
    await call.answer()
    key = call.data.split("_")[2]
    names = {"day": "1 день", "3days": "3 дня", "7days": "7 дней", "30days": "30 дней", "forever": "Навсегда"}
    name = names.get(key, "Подписчики")
    # Для подписчиков на 1 день используем VexBoost (пример)
    vexboost_service_id = None
    if key == "day":
        vexboost_service_id = 1   # реальный ID из VexBoost
    await state.update_data(subtype=name, service_name=f"Подписчики Telegram ({name})", vexboost_service_id=vexboost_service_id)
    await call.message.edit_text(f"Выбраны подписчики Telegram: {name}\nВведите количество (минимум 100):")
    await state.set_state(OrderState.waiting_quantity)

# ----- Реакции -----
@router.callback_query(F.data == "tg_reactions")
async def tg_reactions_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(service_name="Реакции Telegram", platform="telegram", category="reactions")
    kb = InlineKeyboardBuilder()
    reactions = [
        ("Позитивные реакции", "positive"),
        ("Негативные реакции", "negative"),
        ("Реакции из списка", "emoji_list"),
        ("Премиум реакции", "premium"),
        ("Звездные реакции", "stars")
    ]
    for name, key in reactions:
        kb.button(text=name, callback_data=f"tg_react_{key}")
    kb.button(text="◀️ Назад", callback_data="platform_telegram")
    kb.adjust(2)
    await call.message.edit_text("Выберите тип реакций:", reply_markup=kb.as_markup())
    await state.set_state(OrderState.waiting_quantity)

@router.callback_query(F.data.startswith("tg_react_"))
async def tg_reaction_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    key = call.data.split("_")[2]
    names = {
        "positive": "Позитивные", "negative": "Негативные",
        "emoji_list": "Реакции из списка", "premium": "Премиум", "stars": "Звездные"
    }
    name = names.get(key, "Реакции")
    await state.update_data(subtype=name, reaction_type_key=key, service_name=f"Реакции Telegram ({name})")
    await call.message.edit_text(f"Выбраны реакции: {name}\nВведите количество (минимум 1):")
    await state.set_state(OrderState.waiting_quantity)

# ----- Дополнительно -----
@router.callback_query(F.data == "tg_additional")
async def tg_additional_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(service_name="Дополнительно Telegram", platform="telegram", category="additional")
    kb = InlineKeyboardBuilder()
    items = [
        ("Голоса на опрос", "polls"),
        ("Комментарии (свои)", "comments_custom"),
        ("Комментарии по теме поста", "comments_topic"),
        ("Активные подписчики", "active_subs")
    ]
    for name, key in items:
        kb.button(text=name, callback_data=f"tg_add_{key}")
    kb.button(text="◀️ Назад", callback_data="platform_telegram")
    kb.adjust(2)
    await call.message.edit_text("Выберите дополнительную услугу:", reply_markup=kb.as_markup())
    await state.set_state(OrderState.waiting_quantity)

@router.callback_query(F.data.startswith("tg_add_"))
async def tg_additional_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    key = call.data.split("_")[2]
    names = {
        "polls": "Голоса на опрос", "comments_custom": "Комментарии (свои)",
        "comments_topic": "Комментарии по теме поста", "active_subs": "Активные подписчики"
    }
    name = names.get(key, "Дополнительная услуга")
    await state.update_data(subtype=name, service_name=f"Telegram {name}")
    await call.message.edit_text(f"Выбрано: {name}\nВведите количество (минимум 1):")
    await state.set_state(OrderState.waiting_quantity)

# ----- Старты в бота -----
@router.callback_query(F.data == "tg_starts")
async def tg_starts_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(service_name="Старты в бота", platform="telegram", category="starts")
    kb = InlineKeyboardBuilder()
    start_types = [
        ("Принимают реф коды", "ref"),
        ("Просто старт бота", "simple"),
        ("Запуск из поиска", "search"),
        ("ИИ старты", "ai")
    ]
    for name, key in start_types:
        kb.button(text=name, callback_data=f"tg_start_{key}")
    kb.button(text="◀️ Назад", callback_data="platform_telegram")
    kb.adjust(2)
    await call.message.edit_text("Выберите тип стартов:", reply_markup=kb.as_markup())
    await state.set_state(OrderState.waiting_quantity)

@router.callback_query(F.data.startswith("tg_start_"))
async def tg_start_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    key = call.data.split("_")[2]
    names = {
        "ref": "Принимают реф коды", "simple": "Просто старт бота",
        "search": "Запуск из поиска", "ai": "ИИ старты"
    }
    name = names.get(key, "Старты")
    await state.update_data(subtype=name, service_name=f"Старты в бота ({name})")
    await call.message.edit_text(f"Выбраны старты: {name}\nВведите количество (минимум 10):")
    await state.set_state(OrderState.waiting_quantity)

# ====== Общий ввод количества ======
@router.message(OrderState.waiting_quantity)
async def quantity_input(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число!")
    quantity = int(message.text)
    data = await state.get_data()
    # Определяем минимальное количество в зависимости от услуги
    min_q = 1
    if "Подписчики" in data.get('service_name', '') and "Telegram" in data.get('service_name', ''):
        min_q = 100
    elif "Старты" in data.get('service_name', ''):
        min_q = 10
    if quantity < min_q:
        return await message.answer(f"Минимальное количество для выбранной услуги: {min_q}.")
    # Цена пока временно 1 рубль за единицу (позже будет браться из БД)
    price = quantity * 1.0
    await state.update_data(quantity=quantity, price=price)
    await message.answer(f"💰 Стоимость: {price:.2f} руб.\n\nОтправьте ссылку:")
    await state.set_state(OrderState.waiting_link)

# ====== Ввод ссылки ======
@router.message(OrderState.waiting_link)
async def link_input(message: Message, state: FSMContext):
    link = message.text.strip()
    if not validate_link(link):
        return await message.answer("Пожалуйста, отправьте корректную ссылку, начинающуюся с http:// или https://")
    data = await state.get_data()
    order_id = generate_order_id()
    await state.update_data(link=link, order_id=order_id)

    # Проверяем баланс
    balance = await db.get_balance(message.from_user.id)
    price = data['price']
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

    # Показываем подтверждение
    service_desc = data.get('service_name', 'Услуга')
    if data.get('subtype'):
        service_desc += f" ({data['subtype']})"
    text = f"""
<b>Подтвердите заказ</b>

🆔 Номер заказа: {order_id}
📦 Услуга: {service_desc}
🔢 Количество: {data['quantity']}
💰 Цена: {price:.2f} руб.
🔗 Ссылка: {link}

Введите промокод (если есть) или нажмите «Подтвердить» для оплаты.
"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Ввести промокод", callback_data="enter_promocode")
    kb.button(text="✅ Подтвердить заказ", callback_data=f"confirm_order_{order_id}")
    kb.button(text="❌ Отмена", callback_data="back_to_main")
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(OrderState.waiting_confirm)

# ====== Промокоды ======
@router.callback_query(F.data == "enter_promocode")
async def enter_promocode(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Введите промокод:")
    await state.set_state(OrderState.waiting_promocode)

@router.message(OrderState.waiting_promocode)
async def apply_promocode(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    promo = await db.get_promocode(code)
    if not promo:
        return await message.answer("❌ Промокод не найден.")
    if promo[3] and promo[2] >= promo[3]:
        return await message.answer("❌ Промокод уже использован максимальное количество раз.")
    data = await state.get_data()
    price = data['price']
    discount = promo[1]
    new_price = price * (1 - discount/100.0)
    await state.update_data(promocode=code, price=new_price, discount=discount)
    await message.answer(f"✅ Промокод применён! Скидка {discount}%. Новая цена: {new_price:.2f} руб.")
    # Возвращаем к подтверждению
    order_id = data['order_id']
    service_desc = data.get('service_name', 'Услуга')
    if data.get('subtype'):
        service_desc += f" ({data['subtype']})"
    text = f"""
<b>Подтвердите заказ</b>

🆔 Номер заказа: {order_id}
📦 Услуга: {service_desc}
🔢 Количество: {data['quantity']}
💰 Цена (со скидкой): {new_price:.2f} руб.
🔗 Ссылка: {data['link']}
"""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить заказ", callback_data=f"confirm_order_{order_id}")
    kb.button(text="❌ Отмена", callback_data="back_to_main")
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(OrderState.waiting_confirm)

# ====== Подтверждение заказа (списание + VexBoost) ======
@router.callback_query(F.data.startswith("confirm_order_"))
async def confirm_order(call: CallbackQuery, state: FSMContext):
    await call.answer()
    order_id = call.data.split("_")[2]
    data = await state.get_data()
    if data.get('order_id') != order_id:
        await call.message.answer("Ошибка: заказ не найден.")
        return

    # Списываем средства
    balance = await db.get_balance(call.from_user.id)
    if balance < data['price']:
        await call.message.answer("❌ Недостаточно средств. Пополните баланс.")
        return
    await db.update_balance(call.from_user.id, -data['price'])

    service_desc = data.get('service_name', 'Услуга')
    if data.get('subtype'):
        service_desc += f" ({data['subtype']})"

    # Проверяем, нужно ли использовать VexBoost
    vexboost_service_id = data.get('vexboost_service_id')
    if vexboost_service_id:
        # Отправляем заказ в VexBoost
        try:
            vexboost_result = await create_vexboost_order(
                service_id=vexboost_service_id,
                link=data['link'],
                quantity=data['quantity']
            )
            external_order_id = vexboost_result['order']
            await db.update_order_external(order_id, vexboost_service_id, external_order_id, "vexboost")
            await db.update_order_status(order_id, "PROCESSING", "Передано в VexBoost")
            await call.message.edit_text(
                f"✅ Заказ №{order_id} передан в систему накрутки VexBoost.\n"
                f"Ожидайте выполнения. Статус будет обновляться автоматически."
            )
        except VexBoostError as e:
            logger.error(f"VexBoost create order error: {e}")
            # Возвращаем средства
            await db.update_balance(call.from_user.id, data['price'])
            await call.message.edit_text(
                f"❌ Не удалось создать заказ в VexBoost. Средства возвращены.\nОшибка: {e}"
            )
            await state.clear()
            return
    else:
        # Обычный заказ (без внешнего API)
        await db.create_order(
            order_id=order_id,
            user_id=call.from_user.id,
            service_id=data.get('service_id', 0),
            quantity=data['quantity'],
            price=data['price'],
            link=data['link'],
            status="PAID",
            comment=service_desc,
            promocode=data.get('promocode')
        )
        new_balance = balance - data['price']
        await call.message.edit_text(
            f"✅ Заказ №{order_id} успешно оформлен!\n\n"
            f"📦 Услуга: {service_desc}\n"
            f"🔢 Количество: {data['quantity']}\n"
            f"💰 Сумма: {data['price']:.2f} руб.\n"
            f"🔗 Ссылка: {data['link']}\n\n"
            f"💰 Новый баланс: {new_balance:.2f} руб.\n\n"
            "Ваш заказ передан в работу. Ожидайте выполнения."
        )
        # Уведомляем админов
        admins = await db.get_all_admins()
        for admin in admins:
            try:
                await bot.send_message(admin, f"📦 Новый заказ №{order_id} от {call.from_user.id}\nУслуга: {service_desc}\nКоличество: {data['quantity']}\nСумма: {data['price']:.2f} руб.\nСсылка: {data['link']}")
            except:
                pass

    await state.clear()