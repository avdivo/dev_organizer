import sqlite3
import aiosqlite
import threading
from typing import Any, Dict, List, Union, Optional

class SQLiteClient:
    """
    Универсальный клиент SQLite с поддержкой синхронного и асинхронного режимов.
    Инициализируется один раз при старте проекта и работает до окончания.
    """

    _instance = None
    _sync_local = threading.local()

    def __new__(cls, db_path: str):
        """Создание единственного экземпляра (Singleton)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = db_path
        return cls._instance

    def _get_sync_connection(self) -> sqlite3.Connection:
        """Получение синхронного соединения (хранится в потоке)."""
        if not hasattr(self._sync_local, "conn"):
            self._sync_local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._sync_local.conn

    async def _get_async_connection(self) -> aiosqlite.Connection:
        """Получение асинхронного соединения."""
        return await aiosqlite.connect(self.db_path)

    def execute_sync(self, query: str, params: Union[tuple, dict] = ()) -> List[Dict[str, Any]]:
        """Синхронное выполнение SQL-запроса."""
        conn = self._get_sync_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        conn.commit()
        return result

    async def execute_async(self, query: str, params: Union[tuple, dict] = ()) -> List[Dict[str, Any]]:
        """Асинхронное выполнение SQL-запроса."""
        async with await self._get_async_connection() as conn:
            async with conn.execute(query, params) as cursor:
                result = [dict(zip([column[0] for column in cursor.description], row)) async for row in cursor]
            await conn.commit()
        return result


"""
db = SQLiteClient("database.sqlite")

# Выполнение синхронного запроса
result = db.execute_sync("SELECT * FROM users WHERE id=?", (1,))
print(result)


@app.get("/user/{user_id}")
async def get_user(user_id: int):
    db = SQLiteClient("database.sqlite")
    result = await db.execute_async("SELECT * FROM users WHERE id=?", (user_id,))
    return result
"""