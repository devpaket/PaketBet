import asyncio
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

gmrate = 3500
gmrate_direction = "⏸"
gmrate_change_percent = "0.0%"

MoscowTZ = ZoneInfo("Europe/Moscow")

HOLIDAYS = {
    "01-01", "02-23", "03-08", "05-01", "05-09", "06-12", "11-04",
}

def is_holiday_today() -> bool:
    now_msk = datetime.now(MoscowTZ)
    today = now_msk.strftime("%m-%d")
    return today in HOLIDAYS

def get_next_hour_str() -> str:
    now = datetime.now(MoscowTZ)
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return next_hour.strftime("%H:00")

last_update_time = get_next_hour_str()

def update_rate_once():
    global gmrate, gmrate_direction, gmrate_change_percent, last_update_time

    if is_holiday_today():
        min_rate, max_rate = 3700, 6000
    else:
        min_rate, max_rate = 3000, 4000

    old_rate = gmrate

    step = random.randint(50, 150)
    direction = random.choice([1, -1])
    new_rate = gmrate + step * direction

    gmrate = max(min(new_rate, max_rate), min_rate)

    if old_rate != 0:
        change = ((gmrate - old_rate) / old_rate) * 100
    else:
        change = 0.0

    gmrate_change_percent = f"{change:+.1f}%"

    if gmrate > old_rate:
        gmrate_direction = "📈"
    elif gmrate < old_rate:
        gmrate_direction = "📉"
    else:
        gmrate_direction = ""
        gmrate_change_percent = "0.0%"

    last_update_time = datetime.now(MoscowTZ).strftime("%H:00")

    print(f"[Курс обновлён] {gmrate} mCoin {gmrate_direction} {gmrate_change_percent} в {last_update_time} МСК")

async def update_gmrate():
    update_rate_once()

    now = datetime.now(MoscowTZ)
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    wait_seconds = (next_hour - now).total_seconds()
    await asyncio.sleep(wait_seconds)

    while True:
        update_rate_once()
        await asyncio.sleep(3600)
