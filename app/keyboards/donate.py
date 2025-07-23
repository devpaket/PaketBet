from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def donate_keyboards(user_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Купить DC ❤️", callback_data="donation_buy:stars")
            ],
            [
                InlineKeyboardButton(text="💱 Обменник", callback_data=f"exchange_menu:{user_id}")
            ]
        ]
    )

def stars_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="26 DC (13 ⭐)", callback_data="buy_gmp:stars:26"),
                InlineKeyboardButton(text="50 DC", callback_data="buy_gmp:stars:50"),
                InlineKeyboardButton(text="100 DC", callback_data="buy_gmp:stars:100")
            ],
            [
                InlineKeyboardButton(text="250 DC", callback_data="buy_gmp:stars:250"),
                InlineKeyboardButton(text="⚡(-25%) 2000 DC", callback_data="buy_gmp:stars:2000"),
            ],
            [   
                InlineKeyboardButton(text="❤️(-35%) 4000 DC", callback_data="buy_gmp:stars:4000")
            ],
            [   
                InlineKeyboardButton(text="❤️‍🔥(-50%) 20.000 DC ⭐", callback_data="buy_gmp:stars:20000")
            ],
            
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="donation_menu")
            ]
        ]
    )

