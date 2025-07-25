from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command, or_f
from aiogram.enums.parse_mode import ParseMode
from database.queries import get_user, update_user_balance
from database.setup import Database
from config import load_config
import asyncio

router = Router()

config = load_config()
db = Database(config.bot.database)

@router.message(
    or_f(
        Command("dice"),
        F.text.casefold().startswith("кубик")
    )
)
async def dice_handler(message: Message):
    args = message.text.split()
    user_id = message.from_user.id

    if len(args) != 3:
        await message.answer(
            f"🥶 <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"<code>·····················</code>\n"
            f"🎲 <code>/dice</code> <i>[ставка] [1-6/больше/меньше/чет/нечет/все]</i>\n\n"
            f"<i>Пример:</i> <code>/dice 100 2</code>\n"
            f"<i>Пример:</i> <code>кубик 100 больше</code>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    # Парсим ставку
    user = await get_user(db, user_id)
    if not user:
        await message.answer(
            f"❌ <i>{format_user(message)} профиль не найден.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    # Парсим ставку
    bet_input = args[1].lower()
    if bet_input == "все":
        amount = user["balance"]
    else:
        try:
            amount = int(bet_input)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                f"🥶 <i>{format_user(message)} ставка должна быть положительным числом или 'все'.</i>",
                parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
            return

    if amount > user["balance"] or amount == 0:
        await message.answer(
            f"❌ <i>{format_user(message)} у тебя недостаточно средств.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    guess = args[2].lower()

    # Проверка валидности ставки
    valid_guesses = ['1','2','3','4','5','6','больше','меньше','чет','нечет','все']
    if guess not in valid_guesses:
        await message.answer(
            f"🥶 <i>{format_user(message)} неверный выбор (число, больше, меньше, чет, нечет, все).</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    user = await get_user(db, user_id)
    if not user or user["balance"] < amount:
        await message.answer(
            f"❌ <i>{format_user(message)} у тебя недостаточно средств.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    await update_user_balance(db, user_id, user["balance"] - amount)

    # Бросок кубика в Telegram (отправка dice)
    dice_message = await message.answer_dice(emoji="🎲")
    await asyncio.sleep(4)
    dice_value = dice_message.dice.value

    # Определяем результат и коэффициент
    won = False
    coeff = 0.0

    if guess == 'все':
        # Пользователь ставит на "все" — выигрывает всегда с коэффициентом 1
        won = True
        coeff = 1.0
    elif guess in ['чет', 'нечет']:
        is_even = (dice_value % 2 == 0)
        if (guess == 'чет' and is_even) or (guess == 'нечет' and not is_even):
            won = True
            coeff = 1.9
    elif guess in ['больше', 'меньше']:
        if guess == 'больше' and dice_value > 3:
            won = True
            coeff = 1.9
        elif guess == 'меньше' and dice_value < 4:
            won = True
            coeff = 1.9
    else:
        # Это конкретное число от 1 до 6
        if int(guess) == dice_value:
            won = True
            coeff = 4.0

    if won:
        win_amount = int(amount * coeff)
        await update_user_balance(db, user_id, user["balance"] - amount + win_amount)


        await db.execute(
            "UPDATE users SET coins_win = coins_win + ? WHERE user_id = ?",
            (win_amount, user_id)
        )

        status = "win"
        result_text = (
            f"{format_user(message)}, ты угадал! <b>x{coeff}</b> 🥳\n"
            f"<code>·····················</code>\n"
            f"💸 Ставка: {amount} PaketCoin\n"
            f"🎉 Выигрыш: {win_amount} PaketCoin"
        )
    else:
        await db.execute(
            "UPDATE users SET coins_lost = coins_lost + ? WHERE user_id = ?",
            (amount, user_id)
        )

        status = "lose"
        result_text = (
            f"🛑 {format_user(message)} Ты проиграл(-а)!\n"
            f"<code>·····················</code>\n"
            f"💸 Ставка: {amount} PaketCoin\n"
            f"🎲 Выпало: {dice_value}"
        )


    # Логируем игру
    await db.execute(
        "INSERT INTO games (user_id, game_type, bet, status, result) VALUES (?, ?, ?, ?, ?)",
        (user_id, "dice", amount, status, f"{dice_value}")
    )

    await message.answer(result_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def format_user(message: Message) -> str:
    user = message.from_user
    username = user.username
    first_name = user.first_name or "Пользователь"
    if username:
        return f"<a href='https://t.me/{username}'>{first_name}</a>"
    else:
        return first_name
