from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import load_config

config = load_config()

def start_keyboards() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить бота в чат 💬", url=f"https://t.me/{config.bot.bot_username}?startgroup=start")
            ],
            [
                InlineKeyboardButton(text="❤️ Новости", url="https://t.me/PaketBetNews"),
                InlineKeyboardButton(text="⭐ Общий чат", url="https://t.me/obshchalka4"),
            ],
        ]
    )