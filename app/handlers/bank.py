from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, or_f
from aiogram.enums import ParseMode
from datetime import datetime
from database.setup import Database
from config import load_config
from utils.bank import format_name_link, generate_random_account_number

config = load_config()
db = Database(config.bot.database)
router = Router()

from database.queries import (
    get_user,
    get_bank_account,
    get_deposit_account,
)

DEPOSIT_OPTIONS = {
    "1_day":    {"days": 1,  "rate": 1.1,  "fee": 0.0},
    "1_week":   {"days": 7,  "rate": 3.0,  "fee": 1.5},
    "3_weeks":  {"days": 21, "rate": 10.0, "fee": 4.0},
    "1_month":  {"days": 30, "rate": 15.0, "fee": 7.0},
    "3_months": {"days": 90, "rate": 45.0, "fee": 12.0},
}

PERSONAL_ACCOUNT_OPEN_COST = 100
DEPOSIT_ACCOUNT_OPEN_COST = 0
TRANSFER_FEE_PERCENT = 3.0
TRANSFER_DAILY_LIMIT = 3_000_000

HEADER = "🏦 <b>PaketBank</b>\n\n"


# --- Основной банковский счёт ---

@router.message(or_f(
    Command("bank"),
    F.text.casefold() == "банк",
    F.text.casefold() == "информация о банке"
))
async def bank_info(message: Message):
    user_id = message.from_user.id
    user = await get_user(db, user_id)
    bank_account = await get_bank_account(db, user_id)
    deposit_account = await get_deposit_account(db, user_id)
    name = format_name_link(message.from_user)

    if not bank_account:
        await message.answer(
            HEADER +
            f"👤 <b>{name}</b>\n"
            "У вас нет банковского счёта.\n"
            "Создайте его командой <code>/create_bank</code>",
            parse_mode=ParseMode.HTML
        )
        return

    account_number = bank_account["account_number"]
    balance = bank_account["balance"]
    vip_status = "Обычный"  # TODO: добавить логику VIP из user

    if deposit_account:
        deposit_balance = deposit_account["start_balance"]
        deposit_percent = deposit_account["percent"]
        commission = deposit_account["commission"]
        withdraw_possible = "Да"
    else:
        deposit_balance = 0
        deposit_percent = 0
        commission = 0
        withdraw_possible = "Нет депозита"

    text = (
        HEADER +
        f"👤 Игрок, ваш банковский счёт <code>#{account_number}</code>\n\n"
        f"💰 Деньги в банке: {balance}$\n"
        f"💎 Статус VIP: {vip_status}\n"
        f"〽 Процент под депозит: {deposit_percent}%\n"
        f"💱 Комиссия банка: {commission}%\n"
        f"💵 Под депозитом: {deposit_balance} PaketCoins\n"
        f"⏳ Можно снять: {withdraw_possible}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(or_f(
    Command("create_bank"),
    F.text.casefold() == "банк создать",
    F.text.casefold() == "создать счёт"
))
async def create_bank(message: Message):
    user_id = message.from_user.id
    bank_account = await get_bank_account(db, user_id)
    if bank_account:
        await message.answer(HEADER + "ℹ️ У вас уже есть банковский счёт.", parse_mode=ParseMode.HTML)
        return

    user = await get_user(db, user_id)
    if not user or user["balance"] < PERSONAL_ACCOUNT_OPEN_COST:
        await message.answer(HEADER + f"🚫 Недостаточно средств для создания счёта ({PERSONAL_ACCOUNT_OPEN_COST} PaketCoins).", parse_mode=ParseMode.HTML)
        return

    new_balance = user["balance"] - PERSONAL_ACCOUNT_OPEN_COST
    account_number = await generate_random_account_number()

    await db.execute(
        "INSERT INTO bank_accounts (user_id, balance, account_number) VALUES (?, ?, ?)",
        (user_id, 0, account_number)
    )
    await db.execute(
        "UPDATE users SET balance = ? WHERE user_id = ?",
        (new_balance, user_id)
    )

    await message.answer(
        HEADER +
        f"✅ Банковский счёт успешно создан.\n"
        f"Номер счёта: <b>{account_number}</b>\n"
        f"С баланса пользователя списано {PERSONAL_ACCOUNT_OPEN_COST} PaketCoins.\n"
        f"Ваш текущий баланс: <b>{new_balance}</b> PaketCoins.",
        parse_mode=ParseMode.HTML
    )


@router.message(or_f(
    Command("balance_bank"),
    F.text.casefold() == "банк инфо",
    F.text.casefold() == "проверить информацию счета"
))
async def balance_bank(message: Message):
    user_id = message.from_user.id
    bank_account = await get_bank_account(db, user_id)
    if not bank_account:
        await message.answer(HEADER + "❗ У вас нет банковского счёта. Создайте его командой /create_bank", parse_mode=ParseMode.HTML)
        return

    await message.answer(
        HEADER +
        f"🏦 Баланс банковского счёта:\n"
        f"Номер счёта: <b>{bank_account['account_number']}</b>\n"
        f"Баланс: <b>{bank_account['balance']}</b> PaketCoins",
        parse_mode=ParseMode.HTML
    )


@router.message(or_f(
    Command("transfer_bank"),
    F.text.casefold().startswith("банк перевести"),
    F.text.casefold().startswith("перевести"),
))
async def transfer_bank(message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.answer(HEADER + "❗ Использование: /transfer_bank <номер_счёта> <сумма>", parse_mode=ParseMode.HTML)
        return

    user_id = message.from_user.id
    to_account_number = args[1]
    try:
        amount = int(args[2])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(HEADER + "Введите корректную сумму для перевода.", parse_mode=ParseMode.HTML)
        return

    sender_account = await get_bank_account(db, user_id)
    if not sender_account:
        await message.answer(HEADER + "❗ У вас нет банковского счёта.", parse_mode=ParseMode.HTML)
        return

    recipient_account = await db.fetchrow("SELECT * FROM bank_accounts WHERE account_number = ?", (to_account_number,))
    if not recipient_account:
        await message.answer(HEADER + "❗ Счёт получателя не найден.", parse_mode=ParseMode.HTML)
        return

    if amount > TRANSFER_DAILY_LIMIT:
        await message.answer(HEADER + f"❗ Лимит перевода в день — {TRANSFER_DAILY_LIMIT:,} PaketCoins.", parse_mode=ParseMode.HTML)
        return

    fee = int(amount * TRANSFER_FEE_PERCENT / 100)
    total = amount + fee

    if sender_account["balance"] < total:
        await message.answer(HEADER + f"❗ Недостаточно средств. Текущий баланс: {sender_account['balance']} PaketCoins.", parse_mode=ParseMode.HTML)
        return

    new_sender_balance = sender_account["balance"] - total
    new_recipient_balance = recipient_account["balance"] + amount

    await db.execute("UPDATE bank_accounts SET balance = ? WHERE user_id = ?", (new_sender_balance, user_id))
    await db.execute("UPDATE bank_accounts SET balance = ? WHERE user_id = ?", (new_recipient_balance, recipient_account["user_id"]))

    await message.answer(
        HEADER +
        f"✅ Перевод выполнен:\n"
        f"Сумма: <b>{amount:,}</b> PaketCoins\n"
        f"Комиссия: <b>{fee:,}</b> PaketCoins\n"
        f"Ваш баланс: <b>{new_sender_balance:,}</b> PaketCoins",
        parse_mode=ParseMode.HTML
    )


@router.message(or_f(
    Command("replenish_bank"),
    F.text.casefold().startswith("банк пополнить"),
    F.text.casefold().startswith("пополнить счет"),
))
async def replenish_bank(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer(HEADER + "❗ Использование: /replenish_bank <сумма>", parse_mode=ParseMode.HTML)
        return

    user_id = message.from_user.id
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(HEADER + "Введите корректное положительное число для суммы.", parse_mode=ParseMode.HTML)
        return

    user = await get_user(db, user_id)
    if not user:
        await message.answer(HEADER + "❗ Пользователь не найден.", parse_mode=ParseMode.HTML)
        return

    if user["balance"] < amount:
        await message.answer(HEADER + "🚫 Недостаточно средств для пополнения.", parse_mode=ParseMode.HTML)
        return

    bank_account = await get_bank_account(db, user_id)
    if not bank_account:
        await message.answer(HEADER + "❗ Банковский счёт не найден. Создайте его командой /create_bank", parse_mode=ParseMode.HTML)
        return

    new_user_balance = user["balance"] - amount
    new_bank_balance = bank_account["balance"] + amount

    await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_user_balance, user_id))
    await db.execute("UPDATE bank_accounts SET balance = ? WHERE user_id = ?", (new_bank_balance, user_id))

    await message.answer(
        HEADER +
        f"✅ Счёт успешно пополнен на <b>{amount}</b> PaketCoins.\n"
        f"Текущий баланс счёта: <b>{new_bank_balance}</b> PaketCoins.",
        parse_mode=ParseMode.HTML
    )


@router.message(or_f(
    Command("withdraw_bank"),
    F.text.casefold().startswith("банк снять"),
    F.text.casefold().startswith("снять со счета"),
))
async def withdraw_bank(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer(HEADER + "❗ Использование: /withdraw_bank <сумма>", parse_mode=ParseMode.HTML)
        return

    user_id = message.from_user.id
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(HEADER + "Введите корректное положительное число для суммы.", parse_mode=ParseMode.HTML)
        return

    bank_account = await get_bank_account(db, user_id)
    if not bank_account:
        await message.answer(HEADER + "❗ Банковский счёт не найден.", parse_mode=ParseMode.HTML)
        return

    if bank_account["balance"] < amount:
        await message.answer(HEADER + "🚫 Недостаточно средств для снятия.", parse_mode=ParseMode.HTML)
        return

    user = await get_user(db, user_id)
    new_balance = bank_account["balance"] - amount
    new_user_balance = user["balance"] + amount

    await db.execute("UPDATE bank_accounts SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_user_balance, user_id))

    await message.answer(
        HEADER +
        f"✅ Со счёта снято <b>{amount}</b> PaketCoins.\n"
        f"Текущий баланс счёта: <b>{new_balance}</b> PaketCoins.",
        parse_mode=ParseMode.HTML
    )


# --- Депозитный счёт ---

@router.message(or_f(
    Command("information_deposit"),
    F.text.casefold() == "депозит инфо",
    F.text.casefold() == "информация о депозите"
))
async def information_deposit_handler(message: Message):
    info_lines = []
    for k, v in DEPOSIT_OPTIONS.items():
        info_lines.append(
            f"• <b>{k.replace('_', ' ')}</b>: {v['days']} дней, ставка {v['rate']}%, комиссия {v['fee']}%"
        )
    text = HEADER + "📊 <b>Информация по депозитным продуктам:</b>\n\n" + "\n".join(info_lines)
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(or_f(
    Command("create_deposit"),
    F.text.casefold().startswith("депозит создать"),
))
async def create_deposit_handler(message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            HEADER +
            "❗ Использование: /create_deposit <срок>\n"
            "Доступные сроки: " + ", ".join(DEPOSIT_OPTIONS.keys()),
            parse_mode=ParseMode.HTML
        )
        return

    term_key = args[1].strip()
    option = DEPOSIT_OPTIONS.get(term_key)
    if not option:
        await message.answer(
            HEADER +
            "❗ Неверный срок депозита.\n"
            "Доступные сроки: " + ", ".join(DEPOSIT_OPTIONS.keys()),
            parse_mode=ParseMode.HTML
        )
        return

    bank_account = await get_bank_account(db, user_id)
    if not bank_account:
        await message.answer(HEADER + "❗ У вас нет банковского счёта. Создайте его командой /create_bank", parse_mode=ParseMode.HTML)
        return

    deposit_account = await get_deposit_account(db, user_id)
    if deposit_account:
        await message.answer(HEADER + "ℹ️ У вас уже есть активный депозит.", parse_mode=ParseMode.HTML)
        return

    if bank_account["balance"] < DEPOSIT_ACCOUNT_OPEN_COST:
        await message.answer(HEADER + f"🚫 Недостаточно средств для открытия депозита ({DEPOSIT_ACCOUNT_OPEN_COST} PaketCoins).", parse_mode=ParseMode.HTML)
        return

    deposit_start = datetime.utcnow().isoformat()

    await db.execute(
        """
        INSERT INTO deposit_accounts (user_id, term_days, percent, commission, start_balance, start_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            option["days"],
            option["rate"],
            option["fee"],
            DEPOSIT_ACCOUNT_OPEN_COST,
            deposit_start
        )
    )

    new_bank_balance = bank_account["balance"] - DEPOSIT_ACCOUNT_OPEN_COST
    await db.execute(
        "UPDATE bank_accounts SET balance = ? WHERE user_id = ?",
        (new_bank_balance, user_id)
    )

    await message.answer(
        HEADER +
        f"🏦 Депозит на срок <b>{term_key.replace('_', ' ')}</b> с процентной ставкой <b>{option['rate']}%</b> успешно открыт.\n"
        f"С баланса списано {DEPOSIT_ACCOUNT_OPEN_COST} PaketCoins.\n"
        f"Ваш текущий баланс: <b>{new_bank_balance}</b> PaketCoins.",
        parse_mode=ParseMode.HTML
    )


@router.message(or_f(
    Command("replenish_deposit"),
    F.text.casefold().startswith("депозит пополнить")
))
async def replenish_deposit_handler(message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(HEADER + "❗ Использование: /replenish_deposit <сумма>", parse_mode=ParseMode.HTML)
        return

    try:
        amount = int(args[1].strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(HEADER + "Введите корректное положительное число для суммы.", parse_mode=ParseMode.HTML)
        return

    bank_account = await get_bank_account(db, user_id)
    if not bank_account:
        await message.answer(HEADER + "❗ У вас нет банковского счёта.", parse_mode=ParseMode.HTML)
        return

    deposit_account = await get_deposit_account(db, user_id)
    if not deposit_account:
        await message.answer(HEADER + "ℹ️ У вас нет активного депозитного счёта для пополнения.", parse_mode=ParseMode.HTML)
        return

    if bank_account["balance"] < amount:
        await message.answer(HEADER + f"🚫 Недостаточно средств на счёте. Баланс: {bank_account['balance']} PaketCoins.", parse_mode=ParseMode.HTML)
        return

    new_bank_balance = bank_account["balance"] - amount
    new_deposit_balance = deposit_account["start_balance"] + amount

    await db.execute(
        "UPDATE bank_accounts SET balance = ? WHERE user_id = ?",
        (new_bank_balance, user_id)
    )
    await db.execute(
        "UPDATE deposit_accounts SET start_balance = ? WHERE user_id = ?",
        (new_deposit_balance, user_id)
    )

    await message.answer(
        HEADER +
        f"✅ Депозит успешно пополнен на <b>{amount}</b> PaketCoins.\n"
        f"Баланс счёта: <b>{new_bank_balance}</b>\n"
        f"Баланс депозита: <b>{new_deposit_balance}</b> PaketCoins.",
        parse_mode=ParseMode.HTML
    )


@router.message(or_f(
    Command("withdraw_deposit"),
    F.text.casefold().startswith("депозит снять")
))
async def withdraw_deposit_handler(message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(HEADER + "❗ Использование: /withdraw_deposit <сумма>", parse_mode=ParseMode.HTML)
        return

    try:
        amount = int(args[1].strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(HEADER + "Введите корректное положительное число для суммы.", parse_mode=ParseMode.HTML)
        return

    deposit_account = await get_deposit_account(db, user_id)
    if not deposit_account:
        await message.answer(HEADER + "ℹ️ У вас нет активного депозита.", parse_mode=ParseMode.HTML)
        return

    deposit_days = deposit_account["term_days"]
    deposit_start = datetime.fromisoformat(deposit_account["start_date"])
    elapsed_days = (datetime.utcnow() - deposit_start).days

    if elapsed_days < deposit_days:
        await message.answer(
            HEADER +
            f"⏳ Срок депозита ещё не истёк.\n"
            f"Осталось дней: {deposit_days - elapsed_days}.",
            parse_mode=ParseMode.HTML
        )
        return

    if amount > deposit_account["start_balance"]:
        await message.answer(HEADER + "🚫 Запрашиваемая сумма превышает баланс депозита.", parse_mode=ParseMode.HTML)
        return

    bank_account = await get_bank_account(db, user_id)
    new_deposit_balance = deposit_account["start_balance"] - amount
    new_bank_balance = bank_account["balance"] + amount

    await db.execute(
        "UPDATE deposit_accounts SET start_balance = ? WHERE user_id = ?",
        (new_deposit_balance, user_id)
    )
    await db.execute(
        "UPDATE bank_accounts SET balance = ? WHERE user_id = ?",
        (new_bank_balance, user_id)
    )

    await message.answer(
        HEADER +
        f"✅ С депозита снято <b>{amount}</b> PaketCoins.\n"
        f"Баланс депозита: <b>{new_deposit_balance}</b>\n"
        f"Баланс банковского счёта: <b>{new_bank_balance}</b>",
        parse_mode=ParseMode.HTML
    )
