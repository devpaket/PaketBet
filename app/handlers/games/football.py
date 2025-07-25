from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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


@router.message(or_f(Command("football"), F.text.casefold().startswith("футбол")))
async def football_handler(message: Message):
    args = message.text.split()
    if len(args) != 2:
        return await message.answer(
            f"⚽️ <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"<code>·····················</code>\n"
            f"📋 <code>/football</code> <i>[ставка]</i>\n\n"
            f"<i>Пример:</i> <code>/football 100</code>\n"
            f"<i>Пример:</i> <code>футбол все</code>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    user_id = message.from_user.id
    user = await get_user(db, user_id)
    if not user:
        return

    try:
        amount = user["balance"] if args[1].lower() in ("все", "всё") else int(args[1])
    except ValueError:
        return await message.answer(
            f"⚽️ <i>{format_user(message)} ты ввел что-то неправильно!</i>\n"
            f"<code>·····················</code>\n"
            f"📋 <code>/football</code> <i>[ставка]</i>\n\n"
            f"<i>Пример:</i> <code>/football 100</code>\n"
            f"<i>Пример:</i> <code>футбол все</code>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    if amount <= 0:
        return await message.answer(
            f"🥶 <i>{format_user(message)} ставка должна быть больше нуля.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    if user["balance"] < amount:
        return await message.answer(
            f"❌ <i>{format_user(message)} у тебя недостаточно средств.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚽️ Гол - x1.6", callback_data=f"football:goal:{amount}")],
            [InlineKeyboardButton(text="🥅 Мимо - x2.2", callback_data=f"football:miss:{amount}")]
        ]
    )

    await message.answer(
        f"⚽️ {format_user(message)}, выбери исход игры!\n"
        f"<code>·····················</code>\n"
        f"💸 Ставка: <b>{amount}</b> PaketCoin",
        reply_markup=markup,
        parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("football:"))
async def football_result_handler(callback: CallbackQuery):
    data = callback.data.split(":")
    if len(data) != 3:
        return

    choice = data[1]
    amount = int(data[2])
    user_id = callback.from_user.id

    user = await get_user(db, user_id)
    if not user or user["balance"] < amount:
        return await callback.message.edit_text(
            f"❌ <i>{format_user(callback)} у тебя недостаточно средств или данные устарели.</i>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    await update_user_balance(db, user_id, user["balance"] - amount)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)

    
    dice_msg = await callback.message.answer_dice(emoji=DiceEmoji.FOOTBALL)
    await asyncio.sleep(4)

    value = dice_msg.dice.value
    win = 0
    outcome_text = ""
    status = "lose"
    emoji_result = "😢"
    selected_text = "⚽️ Гол" if choice == "goal" else "🥅 Мимо"
    coeff = 1.6 if choice == "goal" else 2.2

    if choice == "goal" and value in (3, 4, 5):
        win = int(amount * coeff)
        status = "win"
        emoji_result = "⚽️"
        outcome_text = f"✅ {format_user(callback)}, мяч попал в ворота! x{coeff} {emoji_result}"
    elif choice == "miss" and value in (1, 2):
        win = int(amount * coeff)
        status = "win"
        emoji_result = "🥅"
        outcome_text = f"✅ {format_user(callback)}, ты угадал мимо! x{coeff} {emoji_result}"
    else:
        outcome_text = f"❌ {format_user(callback)}, ты не угадал! x0 {emoji_result}"

    if win > 0:
        await update_user_balance(db, user_id, user["balance"] + win)
        await db.execute("UPDATE users SET coins_win = coins_win + ? WHERE user_id = ?", (win, user_id))
    else:
        await db.execute("UPDATE users SET coins_lost = coins_lost + ? WHERE user_id = ?", (amount, user_id))

    await db.execute(
        "INSERT INTO games (user_id, game_type, bet, status, result) VALUES (?, ?, ?, ?, ?)",
        (user_id, "football", amount, status, f"value={value}, choice={choice}")
    )

    await callback.message.answer(
        f"{outcome_text}\n"
        f"<code>·····················</code>\n"
        f"💸 Ставка: <b>{amount}</b> PaketCoins\n"
        f"🎲 Выбрано: <b>{selected_text}</b>",
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
