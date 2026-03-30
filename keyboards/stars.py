from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_stars_menu():
    """Клавиатура меню Telegram Звёзды/Премиум."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Телеграм звёзды", callback_data="stars_stars")
    builder.button(text="👑 Телеграм премиум", callback_data="stars_premium")
    builder.button(text="◀️ Назад", callback_data="order")
    builder.adjust(1)
    return builder.as_markup()