
from datetime import datetime, timezone
from typing import Optional
from aiosqlite import Connection
from database.setup import Database

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
    

async def get_last_bonus_time(conn: Connection, user_id: int, bonus_type: str) -> Optional[datetime]:
    query = """
    SELECT claimed_at
    FROM bonus_claims
    WHERE user_id = ? AND type = ?
    ORDER BY claimed_at DESC
    LIMIT 1
    """
    async with conn.execute(query, (user_id, bonus_type)) as cursor:
        row = await cursor.fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None


async def update_last_bonus_time(conn: Connection, user_id: int, bonus_type: str) -> None:
    now = datetime.now().isoformat()
    query = """
    INSERT INTO bonus_claims (user_id, type, claimed_at)
    VALUES (?, ?, ?)
    """
    await conn.execute(query, (user_id, bonus_type, now))
    await conn.commit()

async def get_user(db: Database, user_id: int):
    query = "SELECT * FROM users WHERE user_id = ?"
    return await db.fetchrow(query, (user_id,))


async def update_user_balance(self, user_id: int, new_balance: int):
    await self._conn.execute(
        "UPDATE users SET balance = ? WHERE user_id = ?",
        (new_balance, user_id)
    )
    await self._conn.commit()

async def get_bank_account(db: Database, user_id: int):
    query = "SELECT * FROM bank_accounts WHERE user_id = ?"
    return await db.fetchrow(query, (user_id,))

async def get_deposit_account(db: Database, user_id: int):
    query = "SELECT * FROM deposit_accounts WHERE user_id = ?"
    return await db.fetchrow(query, (user_id,))
