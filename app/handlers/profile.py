from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from database.setup import Database
from config import load_config
from datetime import datetime, timedelta
from random import randint
from database.queries import get_last_bonus_time, update_last_bonus_time

from keyboards.profile import bonus_options_keyboard, invite_bot_keyboard
from keyboards.top import top_main_keyboard, duel_filter_keyboard, mcoin_keyboard

router = Router()

config = load_config()
db = Database(config.bot.database)

@router.message(Command("balance"))
async def balance_handler(message: Message):
    await db.connect()
    user_id = message.from_user.id
    query = """
        SELECT balance, games_played, duels_won, coins_lost
        FROM users
        WHERE user_id = ?
    """
    async with db._conn.execute(query, (user_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        balance, games_played, duels_won, coins_lost = row
        response_text = (
            f"<i>💰Баланс: {balance} PaketCoin</i>\n"
            f"<code>·····················</code>\n"
            f"<i>💣 Сыграно игр: {games_played}</i>\n"
            f"<i>⚔️ Выиграно дуэлей: {duels_won}</i>\n"
            f"<i>🗿 Проиграно PaketCoin: {coins_lost}</i>"
        )
        await db.close()
        await message.answer(response_text, parse_mode=ParseMode.HTML)
    else:
        await message.answer("Пользователь не найден в базе данных.")

@router.message(Command("bonus"))
async def bonus_handler(message: Message):
    await db.connect()
    user = message.from_user
    username = user.username
    first_name = user.first_name
    name_link = f"<a href='https://t.me/{username}'>{first_name}</a>"
    user_id = user.id

    async with db._conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        balance = row[0] if row else 0

    now = datetime.now()
    last_time = await get_last_bonus_time(db._conn, user_id)

    if last_time and now - last_time < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_time)
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes = remainder // 60

        bonus_text = (
            f"🙊<i>{name_link}, ты уже получил бонус! Приходи через</i> "
            f"<i>{hours} ч. {minutes} м.</i> ⏳\n"
            "<code>·····················</code>\n"
            f"<i>💰Баланс: {balance} PaketCoin</i>\n"
            "<blockquote>ℹ️<i> Также ты можешь собрать следующие бонусы </i>👇</blockquote>"
        )

        await message.answer(bonus_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=bonus_options_keyboard(message.from_user.id))
        return

    bonus_amount = randint(1403, 1904)

    await db.connect()
    async with db._conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (bonus_amount, user_id)
    ):
        await db._conn.commit()

    await update_last_bonus_time(db._conn, user_id)

    async with db._conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        balance = row[0] if row else 0

    await db.close()

    text = (
        f"🎁 <i>{name_link}, тебе был выдан бонус в размере: {bonus_amount} PaketCoin</i>!\n"
        f"<code>·····················</code>\n"
        f"💰<i>Баланс: {balance} PaketCoin</i>\n"
        f"<blockquote>ℹ️<i> Также ты можешь собрать следующие бонусы 👇</i></blockquote>"
    )

    await message.answer(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=bonus_options_keyboard(user_id),
        disable_web_page_preview=True
    )


@router.message(Command("give"))
async def give_handler(message: Message):
    user = message.from_user
    sender_id = user.id
    sender_username = user.username or "unknown"
    sender_first_name = user.first_name
    sender_link = f"<a href='https://t.me/{sender_username}'>{sender_first_name}</a>"

    await db.connect()

    if message.chat.type not in ("group", "supergroup"):
        await message.answer(
            "<i>❗️Эта команда работает только в чате с ботом!</i>",
            reply_markup=invite_bot_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await db.close()
        return

    if not message.reply_to_message:
        await message.answer("❗️ Чтобы перевести, нужно ответить на сообщение пользователя, которому хотите отправить средства.", parse_mode=ParseMode.HTML)
        await db.close()
        return

    recipient = message.reply_to_message.from_user
    recipient_id = recipient.id
    recipient_username = recipient.username or "unknown"
    recipient_name = recipient.first_name
    recipient_link = f"<a href='https://t.me/{recipient_username}'>{recipient_name}</a>"

    if sender_id == recipient_id:
        await message.answer("<i>❗️ Чтобы перевести средства, ответьте на сообщение другого пользователя.</i>", parse_mode=ParseMode.HTML)
        await db.close()
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.answer(f"<i>🤖 {sender_link}, ты не ввел корректную сумму для перевода.\nКомиссия на перевод — 15%</i>", parse_mode=ParseMode.HTML)
        await db.close()
        return

    amount = int(args[1])
    if amount <= 0:
        await message.answer(f"<i>🤖 {sender_link}, сумма должна быть положительной!</i>", parse_mode=ParseMode.HTML)
        await db.close()
        return

    async with db._conn.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,)) as cursor:
        sender_row = await cursor.fetchone()
    if not sender_row:
        await message.answer(f"<i>🤖 {sender_link}, у тебя нет баланса для перевода.</i>", parse_mode=ParseMode.HTML)
        await db.close()
        return
    sender_balance = sender_row[0]

    async with db._conn.execute("SELECT 1 FROM users WHERE user_id = ?", (recipient_id,)) as cursor:
        recipient_row = await cursor.fetchone()
    if not recipient_row:
        await message.answer("<i>🥲 Этого пользователя нет в базе данных.</i>", parse_mode=ParseMode.HTML)
        await db.close()
        return

    commission = int(amount * 0.10)
    net_amount = amount - commission 
    total_deduction = amount

    if sender_balance < total_deduction:
        await message.answer("<i>❗️Недостаточно средств для перевода с комиссией.</i>", parse_mode=ParseMode.HTML)
        await db.close()
        return

    await db._conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_deduction, sender_id))
    await db._conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (net_amount, recipient_id))
    await db._conn.commit()

    amount_str = f"{net_amount:,}".replace(",", "'")
    balance_str = f"{sender_balance - total_deduction:,}".replace(",", "'")

    transfer_text = (
        f"➡️ <i>{sender_link}, ты передал {amount} PaketCoin {recipient_link}</i>\n"
        f"<code>·····················</code>\n"
        f"💰<i>Баланс: {balance_str} PaketCoin</i>"
    )

    await message.answer(transfer_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await db.close()


def format_balance_short(amount: int) -> str:
    if amount >= 1_000_000_000:
        val = amount / 1_000_000_000
        suffix = "kkk"
    elif amount >= 1_000_000:
        val = amount / 1_000_000
        suffix = "kk"
    elif amount >= 1_000:
        val = amount / 1_000
        suffix = "k"
    else:
        return f"{amount:,}".replace(",", "'")

    val_str = f"{val:.2f}".rstrip('0').rstrip('.')
    return f"{val_str}{suffix}"

@router.message(Command("top"))
async def top_command(message: Message):
    user_id = message.from_user.id
    await db.connect()

    rows = await db._conn.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = await rows.fetchall()

    pos_row = await db._conn.execute(
        "SELECT COUNT(*) + 1 FROM users WHERE balance > (SELECT balance FROM users WHERE user_id = ?)",
        (user_id,)
    )
    position = (await pos_row.fetchone())[0]
    user_balance_row = await db._conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance = (await user_balance_row.fetchone())[0] if user_balance_row else 0

    emojis = ["🥇", "🥈", "🥉"]

    text = "<b>🏆 Мировой Топ по PaketCoin</b>\n\n"
    for i, row in enumerate(rows, start=1):
        user_id_in_row = row[0]
        balance_value = row[1]
        try:
            user = await message.bot.get_chat(user_id_in_row)
            username = user.first_name or user.username or "—"
            user_link = f"<a href='tg://user?id={user_id_in_row}'>{username}</a>"
        except Exception:
            user_link = f"<a href='tg://user?id=0'>—</a>"

        emoji = emojis[i-1] if i <= 3 else "🏅"
        balance_str = format_balance_short(balance_value)
        text += f"{i}. {emoji} {user_link} | <code>{balance_str} PaketCoin</code>\n"

    text += "\n<code>·······························</code>\n"
    user_link_self = f"<a href='tg://user?id={user_id}'>Ты</a>"
    user_balance_str = format_balance_short(user_balance)
    text += f"{position}. 🎖 {user_link_self} | <code>{user_balance_str} PaketCoin</code>"

    await message.answer(text, reply_markup=top_main_keyboard(user_id), parse_mode=ParseMode.HTML)
    await db.close()

@router.callback_query(F.data.startswith("top:mcoin:"))
async def mcoin_top_callback(callback: CallbackQuery):
    _, _, _, user_id_str = callback.data.split(":")
    user_id = int(user_id_str)
    await db.connect()

    rows = await db._conn.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = await rows.fetchall()

    pos_row = await db._conn.execute(
        "SELECT COUNT(*) + 1 FROM users WHERE balance > (SELECT balance FROM users WHERE user_id = ?)",
        (user_id,)
    )
    position = (await pos_row.fetchone())[0]
    user_balance_row = await db._conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance = (await user_balance_row.fetchone())[0] if user_balance_row else 0

    emojis = ["🥇", "🥈", "🥉"]

    text = "<b>💰 ТОП 10 по PaketCoin:</b>\n\n"
    for i, row in enumerate(rows, start=1):
        user_id_in_row = row[0]
        balance_value = row[1]
        try:
            user = await callback.bot.get_chat(user_id_in_row)
            username = user.first_name or user.username or "—"
            user_link = f"<a href='tg://user?id={user_id_in_row}'>{username}</a>"
        except Exception:
            user_link = f"<a href='tg://user?id=0'>—</a>"

        emoji = emojis[i-1] if i <= 3 else "🏅"
        balance_str = format_balance_short(balance_value)
        text += f"{i}. {emoji} {user_link} | <code>{balance_str} PaketCoin</code>\n"

    text += "\n<code>·······························</code>\n"
    user_link_self = f"<a href='tg://user?id={user_id}'>Ты</a>"
    user_balance_str = format_balance_short(user_balance)
    text += f"{position}. 🎖 {user_link_self} | <code>{user_balance_str} PaketCoin</code>"

    await callback.message.edit_text(text, reply_markup=top_main_keyboard(user_id), parse_mode=ParseMode.HTML)
    await callback.answer()
    await db.close()

@router.callback_query(F.data.startswith("top:duel:"))
async def duel_top_callback(callback: CallbackQuery):
    _, _, scope, user_id_str = callback.data.split(":")
    user_id = int(user_id_str)

    if scope != "all":
        await callback.answer("Этот фильтр не поддерживается. Показывается топ за всё время.", show_alert=True)
        return

    await db.connect()
    rows = await db._conn.execute(
        "SELECT user_id, duels_won FROM users ORDER BY duels_won DESC LIMIT 10"
    )
    rows = await rows.fetchall()

    emojis = ["🥇", "🥈", "🥉"]

    text = "<b>📆 Мировой топ по дуэлям за всё время:</b>\n\n"
    for i, row in enumerate(rows, start=1):
        user_id_in_row = row[0]
        wins = row[1]
        try:
            user = await callback.bot.get_chat(user_id_in_row)
            username = user.first_name or user.username or "—"
            user_link = f"<a href='tg://user?id={user_id_in_row}'>{username}</a>"
        except Exception:
            user_link = f"<a href='tg://user?id=0'>—</a>"

        emoji = emojis[i-1] if i <= 3 else "🏅"
        text += f"{i}. {emoji} {user_link} — {wins} побед\n"

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=duel_filter_keyboard(user_id)
    )
    await callback.answer()
    await db.close()
