from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums.parse_mode import ParseMode
import random
from aiogram.filters import or_f
from database.queries import get_user, update_user_balance
from database.setup import Database
from config import load_config

router = Router()
config = load_config()
db = Database(config.bot.database)


@router.message(
    or_f(
        Command("crash"),
        F.text.casefold().startswith("краш")
    )
)
async def crash_handler(message: Message):
    args = message.text.split()

    if len(args) != 3:
        await message.answer(
            f"🥶 <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"·····················\n"
            f"📈 <code>/crash</code> <i>[ставка] [1.01-10]</i>\n\n"
            f"<i>Пример:</i> <code>/crash 100 1.1</code>\n"
            f"<i>Пример:</i> <code>краш все 1.1</code>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    user_id = message.from_user.id
    user = await get_user(db, user_id)
    if not user:
        return

    try:
        amount = user["balance"] if args[1].lower() in ("все", "всё") else int(args[1])
        target_coeff = float(args[2])
    except ValueError:
        return await message.answer(
            f"🥶 <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"·····················\n"
            f"📈 <code>/crash</code> <i>[ставка] [1.01-10]</i>\n\n"
            f"<i>Пример:</i> <code>/crash 100 1.1</code>\n"
            f"<i>Пример:</i> <code>краш все 1.1</code>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    if amount <= 0 or not (1.01 <= target_coeff <= 10.0):
        return await message.answer(
            f"🥶 <i>{format_user(message)} ставка или коэффициент вне допустимых границ.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    if user["balance"] < amount:
        return await message.answer(
            f"❌ <i>{format_user(message)} у тебя недостаточно средств.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
    real_coeff = round(generate_crash_multiplier(), 2)

    if real_coeff >= target_coeff:
        win = int(amount * target_coeff)
        await update_user_balance(db, user_id, user["balance"] + win)

        # Учёт выигрыша
        await db.execute(
            "UPDATE users SET coins_win = coins_win + ? WHERE user_id = ?",
            (win, user_id)
        )

        result_text = (
            f"🚀 {format_user(message)}, ракета улетела на <b>x{real_coeff}</b> 📈\n"
            f"✅ Ты выиграл! Твой выигрыш составил <b>{win}</b> PaketCoin"
        )
        status = "win"
    else:
        await update_user_balance(db, user_id, user["balance"] - amount)

        # Учёт проигрыша
        await db.execute(
            "UPDATE users SET coins_lost = coins_lost + ? WHERE user_id = ?",
            (amount, user_id)
        )

        result_text = (
            f"🚀 {format_user(message)}, ракета упала на <b>x{real_coeff}</b> 📉\n"
            f"❌ Ты проиграл {amount} PaketCoin"
        )
        status = "lose"

    # Запись игры
    await db.execute(
        "INSERT INTO games (user_id, game_type, bet, status, result) VALUES (?, ?, ?, ?, ?)",
        (user_id, "crash", amount, status, f"x{real_coeff}")
    )

    await message.answer(result_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def generate_crash_multiplier() -> float:
    roll = random.uniform(0, 100)
    if roll < 5:
        return round(random.uniform(8, 10), 2)
    elif roll < 25:
        return round(random.uniform(4, 7.99), 2)
    elif roll < 55:
        return round(random.uniform(2, 3.99), 2)
    elif roll < 85:
        return round(random.uniform(1.5, 1.99), 2)
    else:
        return round(random.uniform(1.00, 1.49), 2)


def format_user(message: Message) -> str:
    user = message.from_user
    username = user.username
    first_name = user.first_name or "Пользователь"
    if username:
        return f"<a href='https://t.me/{username}'>{first_name}</a>"
    else:
        return first_name
