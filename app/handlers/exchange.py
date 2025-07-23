from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters.state import StateFilter

from utils import gmrate
from database.setup import Database
from config import load_config
from keyboards.exchange import exchange_direction_kb, get_confirm_keyboard

config = load_config()
db = Database(config.bot.database)
router = Router()
print("[Log] Router Exchange запущен")

class ExchangeStates(StatesGroup):
    waiting_for_direction = State()
    waiting_for_amount = State()
    waiting_for_confirmation = State()

def format_number(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.2f}k"
    else:
        return str(n)

async def _exchange_core(message: Message, user_id: int):
    await db.connect()
    async with db._conn.execute("SELECT donatecoin, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
    await db.close()

    if not row:
        await message.answer("Пользователь не найден в базе данных.")
        return

    donatecoin, paketcoin = row

    buy_rate = gmrate.gmrate
    sell_rate = round(gmrate.gmrate, 2)

    donatecoin_str = format_number(donatecoin)
    paketcoin_str = format_number(paketcoin)
    buy_rate_str = format_number(buy_rate)
    sell_rate_str = format_number(sell_rate)

    photo = FSInputFile("app/resources/images/change.jpg")
    text = (
        f"💰<i> Ваши балансы:</i>\n"
        f"<code>·····················</code>\n"
        f"<i>DonateCoin: <b>{donatecoin_str}</b></i>\n"
        f"<i>PaketCoin: <b>{paketcoin_str}</b></i>\n\n"
        f"📊<i> Текущий курс обмена:</i>\n"
        f"<blockquote><i>Покупка DonateCoin: <b>Временно недоступно</b></i>\n"
        f"<i>Продажа DonateCoin: <b>1 DC = {sell_rate_str} PaketCoin</b></i></blockquote>\n\n"
        f"<i>Выберите действие:</i>"
    )

    await message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=exchange_direction_kb(),
        parse_mode=ParseMode.HTML
    )

@router.message(or_f(Command("exchange"), F.text.casefold() == "обмен"))
async def cmd_exchange_start(message: Message, state: FSMContext):
    await _exchange_core(message, message.from_user.id)

@router.callback_query(F.data.startswith("exchange_menu:"))
async def callback_exchange_menu(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("Неверный формат callback.")
        return

    target_user_id = int(parts[1])
    actual_user_id = callback.from_user.id

    if actual_user_id != target_user_id:
        await callback.answer("⛔ Это меню не для вас.", show_alert=True)
        return

    await callback.answer()
    await state.clear()
    await _exchange_core(callback.message, actual_user_id)
    await state.set_state(ExchangeStates.waiting_for_direction)


@router.callback_query(
    F.data.startswith("exchange:"),
    StateFilter(ExchangeStates.waiting_for_direction)
)
async def exchange_direction_chosen(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "cancel":
        if callback.message:
            await callback.message.delete()
            await callback.message.answer("Обмен отменён.")
        await state.clear()
        await callback.answer()
        return

    await state.update_data(direction=action)
    text = "💱 <i>Введите сумму для обмена:</i>"
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(ExchangeStates.waiting_for_amount)
    await callback.answer()

@router.message(StateFilter(ExchangeStates.waiting_for_amount))
async def process_exchange_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get("direction")
    user_id = message.from_user.id

    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("🤖 <i>Пожалуйста, введите корректное положительное целое число.</i>", parse_mode=ParseMode.HTML)

    await db.connect()
    async with db._conn.execute("SELECT donatecoin, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        await db.close()
        await state.clear()
        return await message.answer("🤖 <i>Пользователь не найден в базе данных.</i>", parse_mode=ParseMode.HTML)

    donatecoin, paketcoin = row

    buy_rate = gmrate.gmrate
    sell_rate = round(gmrate.gmrate * 0.9, 2)

    if direction == "dc_to_pc":
        if donatecoin < amount:
            await db.close()
            return await message.answer(f"😢 <i>Недостаточно DonateCoin. <b>Ваш баланс: {donatecoin}</b></i>", parse_mode=ParseMode.HTML)
        received_amount = int(amount * buy_rate)
        from_currency = "DonateCoin"
        to_currency = "PaketCoin"
    else:
        if paketcoin < amount:
            await db.close()
            return await message.answer(f"Недостаточно PaketCoin. Ваш баланс: {paketcoin}", parse_mode=ParseMode.HTML)
        received_amount = int(amount / sell_rate)
        from_currency = "PaketCoin"
        to_currency = "DonateCoin"

    if received_amount <= 0:
        await db.close()
        await state.clear()
        return await message.answer("<i>Сумма обмена слишком мала (Минимум 1DC).</i>", parse_mode=ParseMode.HTML)

    await state.update_data(amount=amount, received_amount=received_amount)
    await db.close()

    user = message.from_user
    username = user.username
    first_name = user.first_name
    name_link = f"<a href='https://t.me/{username}'>{first_name}</a>"

    confirm_text = (
        f"<i>{name_link}, Подтвердите обмен:</i>\n"
        f"<code>·····················</code>\n"
        f"🔻 <i>Вы отдаёте: <b>{amount}</b> {from_currency}</i>\n"
        f"🟩 <i>Вы получаете: <b>{received_amount}</b> {to_currency}</i>\n"
        f"<code>·····················</code>\n"
        f"💱 <i>Нажмите кнопку для подтверждения обмена.</i>"
    )
    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        confirm_text, 
        reply_markup=get_confirm_keyboard(), 
        parse_mode=ParseMode.HTML, 
        disable_web_page_preview=True
    )
    await state.set_state(ExchangeStates.waiting_for_confirmation)

@router.callback_query(StateFilter(ExchangeStates.waiting_for_confirmation))
async def confirm_exchange(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    received_amount = data.get("received_amount")
    direction = data.get("direction")
    user_id = callback.from_user.id

    if callback.data == "exchange_cancel":
        if callback.message:
            await callback.message.delete()
            await callback.message.answer("Обмен отменён.")
        await state.clear()
        await callback.answer()
        return

    if callback.data != "exchange_confirm":
        await callback.answer()
        return

    await db.connect()

    if direction == "dc_to_pc":
        column_from = "donatecoin"
        column_to = "balance"
    else:
        column_from = "balance"
        column_to = "donatecoin"

    async with db._conn.execute(f"SELECT {column_from} FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()

    if not row or row[0] < amount:
        await db.close()
        await state.clear()
        if callback.message:
            await callback.message.delete()
            await callback.message.answer("Ошибка: недостаточно средств для обмена.")
        await callback.answer()
        return

    await db._conn.execute(f"UPDATE users SET {column_from} = {column_from} - ? WHERE user_id = ?", (amount, user_id))
    await db._conn.execute(f"UPDATE users SET {column_to} = {column_to} + ? WHERE user_id = ?", (received_amount, user_id))
    await db._conn.commit()
    await db.close()

    await state.clear()
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Обмен выполнен успешно!\n"
            f"Вы обменяли <b>{amount}</b> {'DonateCoin' if column_from == 'donatecoin' else 'PaketCoin'} на <b>{received_amount}</b> "
            f"{'PaketCoin' if column_to == 'balance' else 'DonateCoin'}.",
            parse_mode=ParseMode.HTML
        )
    await callback.answer()
