from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_tiktok_menu():
    """Клавиатура меню TikTok."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Подписчики", callback_data="tt_subscribers")
    builder.button(text="👁 Просмотры", callback_data="tt_views")
    builder.button(text="🔖 Сохранение/репосты", callback_data="tt_saves")
    builder.button(text="👀 Зрители на Трансляцию", callback_data="tt_live_viewers")
    builder.button(text="🤖 Зрители на Трансляцию ИИ", callback_data="tt_live_ai")
    builder.button(text="◀️ Назад", callback_data="order")
    builder.adjust(1)
    return builder.as_markup()