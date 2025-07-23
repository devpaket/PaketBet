from aiogram import Router, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove
from database.queries import create_user, get_user_by_id
from database.setup import Database
from config import load_config
from keyboards.start import start_keyboards

router = Router()

config = load_config()
db = Database(config.bot.database)
print("[Log] Router Menu запущен")

@router.message(Command("start"))
async def cmd_start(message: Message):
    photo = FSInputFile("app/resources/images/start.jpg")
    await db.connect()
    await db.init_tables()

    user = await get_user_by_id(db._conn, message.from_user.id)
    if not user:
        await create_user(db._conn, user_id=message.from_user.id, username=message.from_user.username)    

    text = (
        "<b>Привет</b> 👋 Я PaketBet  👾\n\n"
        "💥 <i>Скоротай время с PaketBet и получай выгоду, прокачивая свой канал и чат. "
        "Играй один, с друзьями или всей семьёй — развлечения на любой вкус!</i>  ⚡️\n\n"
        "🤔 <i>Итак, во что будем играть сегодня? Просто напиши /game, и начинай!</i>\n\n"
        "❓<b>Остались вопросы —</b> 👉 /help 😏"
    )

    await message.answer_photo(photo=photo, caption=text, reply_markup=start_keyboards(), parse_mode=ParseMode.HTML)
    await db.close()

@router.message(Command("game"))
async def play_menu(message: Message):
    user = message.from_user
    username = user.username
    first_name = user.first_name
    name_link = (
        f"<a href='https://t.me/{username}'>{first_name}</a>"
    )

    text = (
        f"<b>🤯 {name_link}, здесь ты можешь поиграть в разные игры!</b>\n"
        "<code>·····················</code>\n"
        "❓ <i>Как запустить игру</i> 👇\n\n"
        "🎰 /casino [ставка]\n"
        "🎲 /dice [ставка] [1-6]\n"
        "📈 /crash [ставка] [1.01-10]\n"
        "💰 /gold [ставка]\n"
        "♠️ /21 [ставка]\n"
        "❌⭕️ /ttt [ставка]\n"
        "🎳 /bowling [ставка]\n"
        "🏀 /basketball [ставка]\n"
        "🎯 /darts [ставка]\n"
        "🎱 /roulette [ставка] [0-36]\n"
        "🐸 /frog [ставка]\n"
        "🎲🎲 /cubes [ставка]\n"
        "🛕 /tower [ставка] [мины 1-4]\n"
        "⚽️ /football [ставка]\n"
        "💠 /diamond [ставка] [мины 1-2]\n\n"
        "Пример: <code>/casino 100</code>\n"
        "Пример: <code>/dice 100 6</code>\n"
        "Пример: <code>/gold 100</code>"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(Command("help"))
async def help_menu(message: Message):
    user = message.from_user
    username = user.username
    first_name = user.first_name
    name_link = (
        f"<a href='https://t.me/{username}'>{first_name}</a>"
    )
    text = (
        f"<i>❓Привет, {name_link} 👾! Здесь собраны все команды, которые тебе могут понадобиться...</i>\n\n"
        "/mines — играть в мины\n"
        "/duel — дуэли\n"
        "/balance — баланс PaketCoin\n"
        "/bonus — бонусные PaketCoin\n"
        "/give — передать PaketCoin\n"
        "/top — топ по PaketCoin\n"
        "/ref — реферальная ссылка\n"
        "/game — игры\n"
        "/case — кейсы\n"
        "/lottery — лотерея\n"
        "/check — чековая книжка\n"
        "/daily — ежедневный бонус\n"
        "/rp — рп команды\n"
        "/ticket — билетная лотерея\n"
        "/donation — купить DonateCoins\n"
        "/exchange — обменник\n"
        "/promote — продвижение\n"
        "<code>·····················</code>\n"
        "👉 <a href='https://telegra.ph/Kak-igrat-v-Miny-bot-05-27'>ПОМОЩЬ ПО ИГРЕ</a>\n"
        "👉 <a href='https://telegra.ph/PRAVILA-GMINESBOT-06-27'>ПРАВИЛА ИГРЫ</a>\n"
        "👉 <a href='https://telegra.ph/FAQ-Miny-bot-08-15'>FAQ</a>"
    )

    await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=start_keyboards())





    
