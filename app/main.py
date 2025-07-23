from aiogram import Bot, Dispatcher
import asyncio

from config import load_config
from database.setup import Database

from handlers.menu import router as menu_router
from handlers.profile import router as profile_router
from handlers.donation import router as donate_router
from handlers.exchange import router as exchange_router

from utils.gmrate import update_gmrate

config = load_config()

async def main():
    bot = Bot(token=config.bot.token)
    dp = Dispatcher()

    db = Database(config.bot.database)
    await db.connect()
    await db.init_tables()

    dp.include_router(menu_router)
    dp.include_router(profile_router)
    dp.include_router(donate_router)
    dp.include_router(exchange_router)

    asyncio.create_task(update_gmrate())
    print("[Log] Обновление курса инициализированно")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close()

if __name__ == '__main__':
    try:
        print('[Log] PaketBet Running')
        asyncio.run(main())
    except KeyboardInterrupt:
        print('[Log] PaketBet Stopping, goodbye')
