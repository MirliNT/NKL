from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_instagram_menu():
    """Клавиатура меню Instagram."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Просмотры", callback_data="ig_views")
    builder.button(text="👥 Подписчики", callback_data="ig_subscribers")
    builder.button(text="❤️ Лайки", callback_data="ig_likes")
    builder.button(text="💬 Комментарии", callback_data="ig_comments")
    builder.button(text="◀️ Назад", callback_data="order")
    builder.adjust(1)
    return builder.as_markup()