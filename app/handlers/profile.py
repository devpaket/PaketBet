from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from database.setup import Database
from config import load_config
import re
from datetime import datetime, timedelta
from random import randint
from database.queries import get_last_bonus_time, update_last_bonus_time
from database.queries import get_user_by_id

from keyboards.profile import bonus_options_keyboard, invite_bot_keyboard
from keyboards.top import top_main_keyboard, duel_filter_keyboard, mcoin_keyboard

router = Router()

config = load_config()
db = Database(config.bot.database)
print("[Log] Router Profile запущен")

@router.message(or_f(Command("balance"), F.text.casefold() == "баланс", F.text.casefold() == "б"))
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

@router.message(or_f(Command("bonus"), F.text.casefold() == "бонус"))
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
    last_time = await get_last_bonus_time(db._conn, user_id, bonus_type='hourly')

    if last_time and now - last_time < timedelta(hours=3):
        remaining = timedelta(hours=3) - (now - last_time)
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes = remainder // 60

        bonus_text = (
            f"🙊<i>{name_link}, ты уже получил бонус! Приходи через</i> "
            f"<i>{hours} ч. {minutes} м.</i> ⏳\n"
            "<code>·····················</code>\n"
            f"<i>💰Баланс: {balance} PaketCoin</i>\n"
            "<blockquote>ℹ️<i> Также ты можешь собрать следующие бонусы </i>👇</blockquote>"
        )

        await message.answer(bonus_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=bonus_options_keyboard(user_id))
        await db.close()
        return

    bonus_amount = randint(100, 600)

    await db._conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (bonus_amount, user_id)
    )
    await db._conn.commit()

    await update_last_bonus_time(db._conn, user_id, bonus_type='hourly')

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
    await process_give(message)

@router.message(F.text.regexp(r"^(передать|Передать|п|П)\s+(\d+|все)$", flags=re.IGNORECASE).as_("match"))
async def give_alias_handler(message: Message, match: re.Match[str]):
    amount_str = match.group(2).lower()
    if amount_str != "все" and not amount_str.isdigit():
        await message.answer("❗️ Укажи корректную сумму или 'все'. Пример: <code>Передать 100</code> или <code>Передать все</code>", parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return
    await process_give(message, amount_str)

async def process_give(message: Message, amount_str: str = None):
    user = message.from_user
    sender_id = user.id
    sender_username = user.username or "unknown"
    sender_first_name = user.first_name
    sender_link = f"<a href='https://t.me/{sender_username}'>{sender_first_name}</a>"

    await db.connect()

    # Проверка типа чата
    if message.chat.type not in ("group", "supergroup"):
        await message.answer(
            "<i>❗️Эта команда работает только в чате с ботом!</i>",
            reply_markup=invite_bot_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    # Проверка, что команда — ответ на сообщение пользователя-получателя
    if not message.reply_to_message:
        await message.answer(
            "❗️ Чтобы перевести, нужно ответить на сообщение пользователя, которому хотите отправить средства.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    recipient = message.reply_to_message.from_user
    recipient_id = recipient.id
    recipient_username = recipient.username or "unknown"
    recipient_name = recipient.first_name
    recipient_link = f"<a href='https://t.me/{recipient_username}'>{recipient_name}</a>"

    if sender_id == recipient_id:
        await message.answer(
            "❗️<i> Чтобы перевести средства, ответьте на сообщение другого пользователя.</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    if amount_str is None:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                f"🤖<i> {sender_link}, ты не ввел корректную сумму для перевода.\nКомиссия на перевод — 10%</i>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            await db.close()
            return
        amount_str = args[1].lower()

    # Проверка баланса отправителя
    async with db._conn.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,)) as cursor:
        sender_row = await cursor.fetchone()
    if not sender_row:
        await message.answer(
            f"🤖<i> {sender_link}, у тебя нет баланса для перевода.</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    # Проверка, что получатель есть в базе
    async with db._conn.execute("SELECT 1 FROM users WHERE user_id = ?", (recipient_id,)) as cursor:
        recipient_row = await cursor.fetchone()
    if not recipient_row:
        await message.answer(
            "🥲<i> Этого пользователя нет в базе данных.</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    sender_balance = sender_row[0]

    if amount_str == "все":
        amount = sender_balance
    else:
        if not amount_str.isdigit():
            await message.answer(
                f"🤖<i> {sender_link}, ты не ввел корректную сумму для перевода.\nКомиссия на перевод — 10%</i>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            await db.close()
            return
        amount = int(amount_str)

    if amount <= 0:
        await message.answer(
            f"🤖<i> {sender_link}, сумма должна быть положительной!</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    commission = int(amount * 0.10)
    net_amount = amount - commission
    total_deduction = amount

    if sender_balance < total_deduction:
        await message.answer(
            "❗️<i>Недостаточно средств для перевода с комиссией.</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await db.close()
        return

    # Обновление балансов
    await db._conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_deduction, sender_id))
    await db._conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (net_amount, recipient_id))

    # Логирование транзакции в таблицу transfers
    sent_at = datetime.utcnow().isoformat()
    await db._conn.execute(
        """
        INSERT INTO transfers (from_user_id, to_user_id, amount, fee, sent_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sender_id, recipient_id, net_amount, commission, sent_at)
    )

    await db._conn.commit()

    balance_str = f"{sender_balance - total_deduction:,}".replace(",", "'")
    amount_str_formatted = f"{net_amount:,}".replace(",", "'")

    transfer_text = (
        f"➡️ <i>{sender_link}, ты передал {amount_str_formatted} PaketCoin {recipient_link}</i>\n"
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

@router.message(or_f(Command("top"), F.text.casefold() == "топ"))
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


@router.message(or_f(
    Command("profile"),
    F.text.in_(["профиль", "я", "Профиль", "Я"])
))
async def profile_handler(message: Message):
    await db.connect()
    user_id = message.from_user.id

    user = message.from_user
    username = user.username
    user_name = user.first_name
    name_link = f"<a href='https://t.me/{username}'>{user_name}</a>"

    # Получаем данные из БД
    rows = await db.fetchall("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = rows[0] if rows else None
    if not user:
        await message.answer("❗️Профиль не найден.")
        return

    # Расчёты и форматирование
    played = user["games_played"]
    wins = user["duels_won"]
    lost = user["coins_lost"]
    balance = user["balance"]
    donatecoin = user["donatecoin"]

    # Место в топе по балансу
    query = """
    SELECT COUNT(*) + 1 AS rank
    FROM users
    WHERE balance > ?
    """
    row = await db.fetchrow(query, (balance,))
    place = row["rank"] if row else "—"

    # Формат даты
    date = datetime.fromisoformat(user["registered_at"]).strftime("%d-%m-%Y %H:%M")

    # Ответ
    text = (
        f"🆔 <i>Профиль: <code>{user_id}</code></i>\n"
        f"<code>·····················</code>\n"
        f"├ 👤 <i>{name_link}</i>\n"
        f"├ ⚡️ <i>Статус: <b>Игрок</b></i>\n"
        f"├ 🎮 <i>Сыграно игр: <b>{played}</b></i>\n"
        f"├ 🏆 <i>Место в топе: <b>{place:,}</b></i>\n"
        f"├ 🟢 <i>Выиграно: <b>{wins:,}</b> PaketCoins</i>\n"
        f"├ 📉 <i>Проиграно: <b>{lost:,}</b> PaketCoins</i>\n"
        f"<blockquote>📅 Дата регистрации: {date}</blockquote>\n"
        f"<code>·····················</code>\n"
        f"💰 <i>Баланс: <b>{balance:,}</b> PaketCoins</i>\n"
        f"💎 <i>Баланс: <b>{donatecoin:,}</b> DonateCoins</i>"
    )

    await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await db.close()