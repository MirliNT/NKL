from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_keyboard_dict():
    """Возвращает словарь inline-клавиатуры с кастомными эмодзи для главного меню."""
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🛒 Заказать накрутку",
                    "callback_data": "order",
                    "icon_custom_emoji_id": "5981010163207772807"
                }
            ],
            [
                {
                    "text": "🧮 Калькулятор",
                    "callback_data": "calc",
                    "icon_custom_emoji_id": "5303214794336125778"
                }
            ],
            [
                {
                    "text": "💰 Пополнить баланс",
                    "callback_data": "balance",
                    "icon_custom_emoji_id": "4958926882994127612"
                }
            ],
            [
                {
                    "text": "👤 Профиль",
                    "callback_data": "profile",
                    "icon_custom_emoji_id": "5258011929993026890"
                }
            ],
            [
                {
                    "text": "🛠 Тех. Поддержка",
                    "callback_data": "support",
                    "icon_custom_emoji_id": "5823268688874179761"
                }
            ],
            [
                {
                    "text": "❓ Частые вопросы",
                    "callback_data": "faq",
                    "icon_custom_emoji_id": "5386720808385142159"
                }
            ]
        ]
    }

# Для обратной совместимости (если где-то используется старый метод) оставим и обычную клавиатуру без иконок
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Заказать накрутку", callback_data="order")
    builder.button(text="🧮 Калькулятор", callback_data="calc")
    builder.button(text="💰 Баланс", callback_data="balance")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🛠 Тех. Поддержка", callback_data="support")
    builder.button(text="❓ Частые вопросы", callback_data="faq")
    builder.adjust(1)
    return builder.as_markup()

def get_back_keyboard():
    """Клавиатура с одной кнопкой «Назад»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    return builder.as_markup()