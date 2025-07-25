from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums.dice_emoji import DiceEmoji
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command, or_f
from database.queries import get_user, update_user_balance
from database.setup import Database
from config import load_config
import asyncio

router = Router()
config = load_config()
db = Database(config.bot.database)


@router.message(or_f(Command("bowling"), F.text.casefold().startswith("боулинг")))
async def bowling_handler(message: Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer(
            f"🥶 {format_user(message)}, ты ввёл команду неправильно!\n"
            f"<code>·····················</code>\n"
            f"🎳 /bowling [ставка]\n\n"
            f"Пример: /bowling 100\n"
            f"Пример: боулинг все",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    user_id = message.from_user.id
    user = await get_user(db, user_id)
    if not user:
        return

    try:
        amount = user["balance"] if args[1].lower() in ("все", "всё") else int(args[1])
    except ValueError:
        await message.answer(
            f"🥶 {format_user(message)}, ставка должна быть числом или 'все'.\n"
            f"<code>·····················</code>\n"
            f"🎳 /bowling [ставка]\n\n"
            f"Пример: /bowling 100\n"
            f"Пример: боулинг все",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    if amount <= 0:
        await message.answer(
            f"🥶 {format_user(message)}, ставка должна быть больше нуля.",
            parse_mode=ParseMode.HTML
        )
        return

    if user["balance"] < amount:
        await message.answer(
            f"❌ {format_user(message)}, у тебя недостаточно средств.",
            parse_mode=ParseMode.HTML
        )
        return

    await update_user_balance(db, user_id, user["balance"] - amount)

    dice_msg = await message.answer_dice(emoji=DiceEmoji.BOWLING)
    await asyncio.sleep(3)

    value = dice_msg.dice.value

    if value in (1, 2):
        coeff = 0
        outcome = "Мимо"
        emoji_res = "🎳"
        win = 0
    elif value == 3:
        coeff = 0.5
        outcome = "Почти все кегли"
        emoji_res = "🎳"
        win = int(amount * coeff)
    elif value in (4, 5):
        coeff = 1
        outcome = "Почти все кегли"
        emoji_res = "🎳"
        win = int(amount * coeff)
    else: 
        coeff = 2
        outcome = "Страйк!"
        emoji_res = "🎉"
        win = int(amount * coeff)

    if win > 0:
        await update_user_balance(db, user_id, user["balance"] + win)
        await db.execute("UPDATE users SET coins_win = coins_win + ? WHERE user_id = ?", (win, user_id))
        status = "win"
    else:
        await db.execute("UPDATE users SET coins_lost = coins_lost + ? WHERE user_id = ?", (amount, user_id))
        status = "lose"

    await db.execute(
        "INSERT INTO games (user_id, game_type, bet, status, result) VALUES (?, ?, ?, ?, ?)",
        (user_id, "bowling", amount, status, f"value={value}, coeff={coeff}")
    )

    await message.answer(
        f"<i>{format_user(message)}, {outcome} <b>(x{coeff})</b> {emoji_res}\n"
        f"<code>·····················</code>\n"
        f"💸 Ставка: <b>{amount}</b> PaketCoins\n"
        f"🎉 Выигрыш: <b>{win}</b> PaketCoins</i>",
        parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


def format_user(message_or_callback) -> str:
    user = message_or_callback.from_user
    username = user.username
    first_name = user.first_name or "Игрок"
    if username:
        return f"<a href='https://t.me/{username}'>{first_name}</a>"
    else:
        return first_name
