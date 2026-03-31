from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_instance import bot
from config import OWNER_ID, PHOTO_PATH
from keyboards import get_main_keyboard
import database as db
import logging

router = Router()
logger = logging.getLogger(__name__)

# ====== Вспомогательные функции ======
async def is_bot_available(user_id: int) -> bool:
    """Проверяет доступность бота для пользователя (админы и владелец всегда могут использовать)."""
    if user_id == OWNER_ID or await db.is_admin(user_id):
        return True
    if await db.is_banned(user_id):
        return False
    return await db.is_bot_active()

async def check_ban_and_terms(user_id: int) -> bool:
    """Проверяет бан и принятие оферты. Возвращает True, если доступ запрещён."""
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
    """Отправляет главное меню с фото (если есть) и кнопками."""
    balance = await db.get_balance(chat_id)
    text = f"""
<b>Приветствую!</b> <tg-emoji emoji-id="5877700484453634587">✈️</tg-emoji>
<b>Добро пожаловать в бота для накрутки статистики пользователей, просмотров и реакций

</b><blockquote><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Тех.поддержка: </b>@nBoost_supports<b>
</b><tg-emoji emoji-id="5870995486453796729">📊</tg-emoji> <b>Наш канал: </b>@channel_username</blockquote>
<a href="https://t.me/your_offer_link">Договор оферты</a> • <a href="https://t.me/your_terms_link">Пользовательское соглашение</a>

<b>💰 Ваш баланс: {balance:.2f} руб.</b>
    """
    kb = get_main_keyboard()
    try:
        photo = FSInputFile(PHOTO_PATH)
        await bot.send_photo(chat_id, photo, caption=text, reply_markup=kb, parse_mode="HTML")
    except FileNotFoundError:
        await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

# ====== Хендлеры ======
@router.message(Command("start"))
async def start_handler(message: Message):
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