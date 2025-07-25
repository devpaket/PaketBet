from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_bank_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [  # Отдельно важная кнопка
            InlineKeyboardButton(text="🔐 Открыть счёт", callback_data="bank:open_account")
        ],
        [  # Отдельно важная кнопка
            InlineKeyboardButton(text="📥 Создать депозит", callback_data="bank:create_deposit")
        ],
        [  # Вспомогательные действия в один ряд
            InlineKeyboardButton(text="💸 Снять депозит", callback_data="bank:withdraw_deposit"),
            InlineKeyboardButton(text="📊 Баланс", callback_data="bank:balance")
        ],
    ])


def get_deposit_term_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗓 1 день", callback_data="deposit:1_day"),
            InlineKeyboardButton(text="🗓 1 неделя", callback_data="deposit:1_week")
        ],
        [
            InlineKeyboardButton(text="🗓 3 недели", callback_data="deposit:3_weeks"),
            InlineKeyboardButton(text="🗓 1 месяц", callback_data="deposit:1_month")
        ],
        [
            InlineKeyboardButton(text="🗓 3 месяца", callback_data="deposit:3_months")
        ],
    ])
