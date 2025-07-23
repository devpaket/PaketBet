
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def exchange_direction_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Купить (Недоступно)", callback_data="exchange:pc_to_dcс"),
                InlineKeyboardButton(text="🔴 Продать", callback_data="exchange:dc_to_pc"),

            ],
            [
                InlineKeyboardButton(text="Отмена", callback_data="exchange:cancel")
            ]
        ]
    )

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Подтвердить", callback_data="exchange_confirm"),
            InlineKeyboardButton(text="🔴 Отмена", callback_data="exchange_cancel"),
        ]
    ])