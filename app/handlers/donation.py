from aiogram import Router, F, types
from aiogram.types import Message, FSInputFile, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from utils import gmrate
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder  
from keyboards.donate import donate_keyboards, stars_keyboard
from database.setup import Database
from config import load_config


config = load_config()
db = Database(config.bot.database)

router = Router()
print("[Log] Router Donation запущен")

async def send_donation_menu(message: Message):
    photo = FSInputFile("app/resources/images/donate.jpg")
    text = (
        f"🛍 <b>Донат-меню</b> 🛒\n"
        f"<code>---------------------</code>\n"
        f"🏧 <i>Курс обмена:</i>\n"
        f"<b>⭐️ = 2 DonateCoin</b>\n"
        f"<i>1 DonateCoin ≈ {gmrate.gmrate} PaketCoin</i> {gmrate.gmrate_direction} <b>({gmrate.gmrate_change_percent})</b>\n"
        f"\n"
        f"<i>💎 Оптовая покупка:</i>\n"
        f"<b>750 ⭐️ = 2000 DonateCoin</b>\n"
        f"<b>1300 ⭐️ = 4000 DonateCoin</b>\n"
        f"<b>5000 ⭐️ = 20'000 DonateCoin</b>\n"
        f"<code>---------------------</code>\n"
        f"<i>⚡️ Спасибо что поддерживаете наш проект! Каждая вложенная вами копейка улучшает бота. 💫</i>"
    )
    user_id = message.from_user.id
    await message.answer_photo(photo=photo, caption=text, parse_mode=ParseMode.HTML, reply_markup=donate_keyboards(user_id), disable_web_page_preview=True)

@router.message(Command("donation"))
async def donation_command(message: Message):
    await send_donation_menu(message)

@router.message(F.text.casefold().in_(["донат"]))
async def donation_text(message: Message):
    await send_donation_menu(message)

@router.callback_query(lambda c: c.data == "donation_menu")
async def donation_callback(callback: CallbackQuery):
    photo = FSInputFile("app/resources/images/donate.jpg")
    text = (
        f"🛍 <b>Донат-меню</b> 🛒\n"
        f"<code>---------------------</code>\n"
        f"🏧 <i>Курс обмена:</i>\n"
        f"<b>⭐️ = 2 DonateCoin</b>\n"
        f"<i>1 DonateCoin ≈ {gmrate.gmrate} PaketCoin</i> {gmrate.gmrate_direction} <b>({gmrate.gmrate_change_percent})</b>\n"
        f"\n"
        f"<i>💎 Оптовая покупка:</i>\n"
        f"<b>750 ⭐️ = 2000 DonateCoin</b>\n"
        f"<b>1300 ⭐️ = 4000 DonateCoin</b>\n"
        f"<b>5000 ⭐️ = 20'000 DonateCoin</b>\n"
        f"<code>---------------------</code>\n"
        f"<i>⚡️ Спасибо что поддерживаете наш проект! Каждая вложенная вами копейка улучшает бота. 💫</i>"
    )  
    user_id = callback.from_user.id
    await callback.message.edit_media(media=types.InputMediaPhoto(media=photo, caption=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True))
    await callback.message.edit_reply_markup(reply_markup=donate_keyboards(user_id))
    await callback.answer()


@router.callback_query(lambda c: c.data == "donation_buy:stars")
async def donation_buy_callback(callback: CallbackQuery):
    user = callback.from_user
    username = user.username or "unknown"
    first_name = user.first_name
    name_link = f"<a href='https://t.me/{username}'>{first_name}</a>"
    photo = FSInputFile("app/resources/images/donate.jpg")
    text = (
        f"💎 <i>{name_link}, сколько DonateCoin ты хочешь купить?</i>\n"
        f"<code>·····················</code>\n"
        f"<blockquote>📊 <b>1 ⭐️ = 2 DonateCoin</b></blockquote>\n"
        f"<blockquote>ℹ️<i> Напишите сумму в DC, которую вы хотите задонатить, или выберите один из вариантов ниже </i>👇</blockquote>\n"
        f"<a href='https://telegra.ph/Politika-vozvrata-sredstv-12-30'> <i>*политика возврата*</i></a>"
    )
    await callback.message.edit_media(media=types.InputMediaPhoto(media=photo, caption=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True))
    await callback.message.edit_reply_markup(reply_markup=stars_keyboard())
    await callback.answer()

def payment_keyboard(stars):  
    builder = InlineKeyboardBuilder()  
    builder.button(text=f"Оплатить {stars} ⭐️", pay=True)

@router.callback_query(F.data.startswith("buy_gmp:stars:"))
async def handle_donation_stars(callback: CallbackQuery):
    _, _, dc_str = callback.data.split(":")
    dc_amount = int(dc_str)

    if dc_amount == 2000:
        stars = 750  # -25%
    elif dc_amount == 4000:
        stars = 1300  # -35%
    elif dc_amount == 20000:
        stars = 5000  # -50%
    else:
        stars = dc_amount // 2 

    prices = [LabeledPrice(label="DonateCoin", amount=stars)]

    await callback.message.answer_invoice(
        title="Покупка DonateCoin",
        description=f"Покупка {dc_amount} DC за {stars} ⭐",
        provider_token="",
        currency="XTR",
        prices=prices,
        payload=f"donate_dc:{dc_amount}",
    )

    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    dc_amount = int(message.successful_payment.invoice_payload.split(":")[1])
    user_id = message.from_user.id

    await db.connect()
    query = "UPDATE users SET donatecoin = donatecoin + ? WHERE user_id = ?"
    await db._conn.execute(query, (dc_amount, user_id))
    await db._conn.commit()

    await db.close()

    await message.answer(
        f"✅<i> На ваш баланс зачисленно <b>{dc_amount} DonateCoin!</b></i>\n<b>Спасибо за поддержку</b> ❤️", 
        parse_mode=ParseMode.HTML
    )