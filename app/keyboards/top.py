from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def top_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Топ по дуэлям", callback_data=f"top:duel:all:{user_id}")
            ]
        ]
    )

def duel_filter_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Топ по PaketCoin", callback_data=f"top:mcoin:all:{user_id}")
            ]
        ]
    )

def mcoin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Топ по дуэлям", callback_data=f"top:duel:all:{user_id}")
            ]
        ]
    )
