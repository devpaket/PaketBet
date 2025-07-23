from aiogram import Bot, Dispatcher
import asyncio

from config import load_config
from database.setup import Database

from handlers.menu import router as menu_router
from handlers.profile import router as profile_router

config = load_config()

async def main():
    bot = Bot(token=config.bot.token)
    dp = Dispatcher()

    db = Database(config.bot.database)
    await db.connect()
    await db.init_tables()

#Сюда вставить роутеры
    dp.include_routers(menu_router,
                       profile_router)

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
