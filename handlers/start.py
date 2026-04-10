import os
import logging
import aiohttp
import json
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_instance import bot
from config import OWNER_ID, PHOTO_PATH, BOT_TOKEN
from keyboards.main import get_main_keyboard_dict
import database as db

router = Router()
logger = logging.getLogger(__name__)

# ====== Вспомогательные функции ======
async def is_bot_available(user_id: int) -> bool:
    if user_id == OWNER_ID or await db.is_admin(user_id):
        return True
    if await db.is_banned(user_id):
        return False
    return await db.is_bot_active()

async def check_ban_and_terms(user_id: int) -> bool:
    if not await is_bot_available(user_id):
        bot_status = await db.get_bot_status()
        if bot_status.get('active') == '0':
            reason = bot_status.get('reason', 'Бот временно недоступен.')
            await bot.send_message(user_id, f"❌ {reason}")
        else:
            await bot.send_message(user_id, "❌ Бот временно недоступен. Попробуйте позже.")
        return True

    ban_info = await db.get_ban_info(user_id)
    if ban_info and ban_info[0] == 1:
        ban_reason = ban_info[3] or "Не указана"
        await bot.send_message(user_id, f"❌ Вы заблокированы.\nПричина: {ban_reason}")
        return True

    if not await db.has_accepted_terms(user_id):
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

async def show_main_menu(chat_id: int):
    balance = await db.get_balance(chat_id)
    text = f"""
<b>Приветствую!</b> <tg-emoji emoji-id="5877700484453634587">✈️</tg-emoji>
<b>Добро пожаловать в бота для накрутки статистики пользователей, просмотров и реакций

</b><blockquote><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Тех.поддержка: </b>@nBoost_supports<b>
</b><tg-emoji emoji-id="5870995486453796729">📊</tg-emoji> <b>Наш канал: </b>@channel_username</blockquote>
<a href="https://t.me/your_offer_link">Договор оферты</a> • <a href="https://t.me/your_terms_link">Пользовательское соглашение</a>

<b>💰 Ваш баланс: {balance:.2f} руб.</b>
    """
    reply_markup = get_main_keyboard_dict()
    async with aiohttp.ClientSession() as session:
        if os.path.exists(PHOTO_PATH):
            form_data = aiohttp.FormData()
            form_data.add_field('chat_id', str(chat_id))
            form_data.add_field('caption', text)
            form_data.add_field('parse_mode', 'HTML')
            form_data.add_field('reply_markup', json.dumps(reply_markup))
            form_data.add_field('photo', open(PHOTO_PATH, 'rb'), filename='photo.jpg')
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
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
                "disable_web_page_preview": True
            }
            await session.post(url, json=payload)

# ====== Хендлеры ======
@router.message(Command("start"))
async def start_handler(message: Message):
    logger.info(f"Start command from {message.from_user.id}")
    await db.add_user(message.from_user.id)
    if await check_ban_and_terms(message.from_user.id):
        return
    await show_main_menu(message.chat.id)

@router.callback_query(F.data == "accept_terms")
async def accept_terms_callback(call: CallbackQuery):
    await call.answer()
    await db.accept_terms(call.from_user.id)
    await call.message.edit_text("✅ Вы приняли договор оферты и политику конфиденциальности. Теперь вы можете пользоваться ботом.")
    await show_main_menu(call.from_user.id)

# ====== Профиль и его подразделы ======
@router.callback_query(F.data == "profile")
async def profile_menu(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    balance = await db.get_balance(user_id)
    reg_date = await db.get_user_reg_date(user_id)
    if reg_date:
        reg_str = reg_date.strftime("%d.%m.%Y %H:%M")
    else:
        reg_str = "неизвестно"
    spent = await db.get_user_spent(user_id)
    orders_count = await db.get_user_orders_count(user_id)
    if user_id == OWNER_ID:
        role = "👑 Владелец"
    elif await db.is_admin(user_id):
        role = "⭐ Администратор"
    else:
        role = "👤 Пользователь"

    text = f"""
<b>👤 Ваш профиль</b>

🆔 <b>ID:</b> {user_id}
💰 <b>Баланс:</b> {balance:.2f} руб.
💸 <b>Потрачено всего:</b> {spent:.2f} руб.
📦 <b>Выполнено заказов:</b> {orders_count}
📅 <b>Дата регистрации:</b> {reg_str}
🔰 <b>Статус:</b> {role}
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 История пополнений", callback_data="profile_topup_history")],
        [InlineKeyboardButton(text="📋 История заказов", callback_data="profile_orders_history")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "profile_topup_history")
async def profile_topup_history(call: CallbackQuery):
    await call.answer()
    txs = await db.get_transactions(call.from_user.id, 20)
    if not txs:
        text = "📜 История пополнений пуста."
    else:
        text = "📜 <b>История пополнений (последние 20):</b>\n"
        for tx in txs:
            status_emoji = "✅" if tx[4] == "success" else "❌"
            text += f"{status_emoji} {tx[6][:10]} +{tx[2]:.2f} руб. ({tx[3]})\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="profile")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "profile_orders_history")
async def profile_orders_history(call: CallbackQuery):
    await call.answer()
    orders = await db.get_user_orders(call.from_user.id, 20)
    if not orders:
        text = "📋 История заказов пуста."
    else:
        text = "📋 <b>История заказов (последние 20):</b>\n"
        for order in orders:
            status_emoji = {
                "PAID": "✅", "ACCEPTED": "📦", "DECLINED": "❌",
                "PROCESSING": "🔄", "WAITING_CONFIRM": "🕒", "NEW": "🆕"
            }.get(order[6], "❓")
            service_name = order[7] if order[7] else f"Услуга #{order[2]}"
            text += f"{status_emoji} {order[0]} – {service_name} x{order[3]} – {order[4]:.2f} руб. ({order[11][:10]})\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="profile")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")