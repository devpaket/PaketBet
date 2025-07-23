from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import load_config

config = load_config()

def bonus_options_keyboard(userid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Лотерея 💼", callback_data=f"lottery_check:{userid}")
            ],
            [
                InlineKeyboardButton(text="🏝️ Ежедневный бонус", callback_data=f"daily_gift_check:{userid}")
            ],
        ]
    )

def invite_bot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить в группу",
                    url=f"https://t.me/{config.bot.bot_username}?startgroup=start"
                )
            ]
        ]
    )