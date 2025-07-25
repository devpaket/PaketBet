from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import or_f
import random

from database.queries import get_user, update_user_balance
from database.setup import Database
from config import load_config

router = Router()

config = load_config()
db = Database(config.bot.database)


@router.message(
    or_f(
        Command("casino"),
        F.text.casefold().startswith("казино")
    )
)
async def casino_handler(message: Message):
    args = message.text.split()

    if len(args) != 2:
        await message.answer(
            f"🥶 <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"·····················\n"
            f"🎰 <code>/casino</code> <i>[ставка]</i>\n\n"
            f"<i>Пример:</i> <code>/casino 100</code>\n"
            f"<i>Пример:</i> <code>казино 100</code>\n",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    user_id = message.from_user.id
    user = await get_user(db, user_id)
    if not user:
        return await message.answer(
            f"❌ <i>{format_user(message)} ты не зарегистрирован в системе.</i>",
            parse_mode=ParseMode.HTML
        )

    balance = user["balance"]

    try:
        if args[1].lower() in ["все", "всё"]:
            amount = balance
        else:
            amount = int(args[1])
    except ValueError:
        return await message.answer(
            f"🥶 <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"<code>·····················</code>\n"
            f"🎰 <code>/casino</code> <i>[ставка]</i>\n\n"
            f"<i>Пример:</i> <code>/casino 100</code>\n"
            f"<i>Пример:</i> <code>казино 100</code>\n"
            f"<i>Пример:</i> <code>/casino все</code>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    if amount <= 0:
        return await message.answer(
            f"🥶 <i>{format_user(message)} ставка должна быть положительной.</i>",
            parse_mode=ParseMode.HTML
        )
    if balance < amount:
        return await message.answer(
            f"❌ <i>{format_user(message)} у тебя недостаточно средств.</i>",
            parse_mode=ParseMode.HTML
        )

    await update_user_balance(db, user_id, balance - amount)

    coeff = round(generate_casino_multiplier(), 2)
    winnings = int(amount * coeff)

    if coeff >= 1:
        await update_user_balance(db, user_id, balance - amount + winnings)
        await db.execute(
            "UPDATE users SET coins_win = coins_win + ? WHERE user_id = ?",
            (winnings, user_id)
        )
        status = "win"
    else:
        await db.execute(
            "UPDATE users SET coins_lost = coins_lost + ? WHERE user_id = ?",
            (amount, user_id)
        )
        status = "lose"

    await db.execute(
        "INSERT INTO games (user_id, game_type, bet, status, result) VALUES (?, ?, ?, ?, ?)",
        (user_id, "casino", amount, status, f"x{coeff}")
    )

    # Всегда отображаем как выигрыш
    result_text = (
        f"{format_user(message)}\n"
        f"🟢 Тебе выпало <b>x{coeff}</b>!\n"
        f"Твой выигрыш составил <b>{winnings}</b> PaketCoin!"
    )

    await message.answer(result_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def generate_casino_multiplier() -> float:
    roll = random.uniform(0, 100)

    if roll < 0.5:  # 0.5%
        return round(random.uniform(5.0, 10.0), 2)
    elif roll < 2.0:  # 1.5%
        return round(random.uniform(2.5, 4.99), 2)
    elif roll < 5.0:  # 3% 
        return round(random.uniform(1.5, 2.49), 2)
    elif roll < 90.0:  # 85%
        return round(random.uniform(0.5, 1.49), 2)
    else:  # 10%
        return round(random.uniform(0.1, 0.49), 2)



def format_user(message: Message) -> str:
    user = message.from_user
    username = user.username
    first_name = user.first_name or "Пользователь"
    if username:
        return f"<a href='https://t.me/{username}'>{first_name}</a>"
    else:
        return first_name
