import aiosqlite
from contextlib import asynccontextmanager
from .models import USERS_TABLE_SCHEMA

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None

    async def fetchall(self, query: str, params: tuple = ()):
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def fetchrow(self, query: str, params: tuple = ()):
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def connect(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row  # 👈 ВКЛЮЧАЕМ доступ по ключам
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def init_tables(self):
        await self._conn.executescript(USERS_TABLE_SCHEMA)
        await self._conn.commit()

    @asynccontextmanager
    async def transaction(self):
        await self._conn.execute("BEGIN")
        try:
            yield
        except Exception:
            await self._conn.execute("ROLLBACK")
            raise
        else:
            await self._conn.execute("COMMIT")
