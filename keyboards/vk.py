from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_vk_menu():
    """Клавиатура меню VK."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Подписчики", callback_data="vk_subscribers")
    builder.button(text="❤️ Лайки", callback_data="vk_likes")
    builder.button(text="👁 Просмотры", callback_data="vk_views")
    builder.button(text="🗳 Голоса на опрос (медленные)", callback_data="vk_polls")
    builder.button(text="◀️ Назад", callback_data="order")
    builder.adjust(1)
    return builder.as_markup()