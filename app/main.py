from aiogram import Bot, Dispatcher
import asyncio
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from database.setup import Database

from handlers.menu import router as menu_router
from handlers.profile import router as profile_router
from handlers.donation import router as donate_router
from handlers.exchange import router as exchange_router
from handlers.bank import router as bank_router

from handlers.games.crash import router as crash_game
from handlers.games.casino import router as casino_game
from handlers.games.dice import router as dice_game
from handlers.games.football import router as football_game
from handlers.games.darts import router as darts_game
from handlers.games.bowling import router as bowling_game
from handlers.games.basketball import router as basketball_game

from utils.gmrate import update_gmrate

config = load_config()

async def main():
    bot = Bot(token=config.bot.token)
    dp = Dispatcher(storage=MemoryStorage())

    db = Database(config.bot.database)
    await db.connect()
    await db.init_tables()

    dp.include_router(menu_router)
    dp.include_router(profile_router)
    dp.include_router(donate_router)
    dp.include_router(exchange_router)
    dp.include_router(bank_router)

    dp.include_router(football_game)
    dp.include_router(crash_game)
    dp.include_router(casino_game)
    dp.include_router(dice_game)
    dp.include_router(darts_game)
    dp.include_router(bowling_game)
    dp.include_router(basketball_game)

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
        print('[Log] KeyboardInterrupt, завершаем...')

        async def shutdown():
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            [task.cancel() for task in tasks]
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)
            except asyncio.TimeoutError:
                print('[Warn] Завершение по таймауту')

        asyncio.run(shutdown())
        print('[Log] PaketBet Stopped, goodbye')
