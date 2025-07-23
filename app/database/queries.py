
from datetime import datetime, timezone
from typing import Optional
from aiosqlite import Connection

#Тут пишите Функции базы данных

async def create_user(
    conn: Connection,
    user_id: int,
    username: Optional[str] = None,
    ref_by: Optional[int] = None
) -> None:
    query_check = "SELECT 1 FROM users WHERE user_id = ?;"
    cursor = await conn.execute(query_check, (user_id,))
    exists = await cursor.fetchone()
    if exists:
        return

    query_insert = """
    INSERT INTO users (user_id, username, ref_by, registered_at, balance)
    VALUES (?, ?, ?, ?, ?);
    """
    registered_at = datetime.now(timezone.utc).isoformat()
    initial_balance = 100

    await conn.execute(query_insert, (user_id, username, ref_by, registered_at, initial_balance))
    await conn.commit()

async def get_user_by_id(conn: Connection, user_id: int) -> Optional[dict]:
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        return row
    

async def get_last_bonus_time(conn: Connection, user_id: int) -> datetime | None:
    async with conn.execute("SELECT last_bonus_at FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

async def update_last_bonus_time(conn: Connection, user_id: int):
    await conn.execute(
        "UPDATE users SET last_bonus_at = ? WHERE user_id = ?",
        (datetime.now().isoformat(), user_id)
    )
    await conn.commit()