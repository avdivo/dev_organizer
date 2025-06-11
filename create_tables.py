import sqlite3
import aiosqlite


class SQLiteTableCreator:
    """
    Модуль для создания таблиц в SQLite.
    Поддерживает синхронное и асинхронное выполнение запросов.
    """

    def __init__(self, db_path: str):
        """Инициализирует путь к базе данных."""
        self.db_path = db_path

    def create_tables_sync(self) -> None:
        """Создает таблицы `users` и `user_lists` в синхронном режиме."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            telegram_id TEXT UNIQUE,
            alice_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Таблица списков, связанных с пользователем
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            list_name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        conn.commit()
        conn.close()
        print("✅ Таблицы `users` и `user_lists` созданы (синхронно).")

    async def create_tables_async(self) -> None:
        """Создает таблицы `users` и `user_lists` в асинхронном режиме."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                telegram_id TEXT UNIQUE,
                alice_id TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                list_name TEXT NOT NULL,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """)

            await conn.commit()
        print("✅ Таблицы `users` и `user_lists` созданы (асинхронно).")


# Пример использования
if __name__ == "__main__":
    db_path = "database.sqlite"
    table_creator = SQLiteTableCreator(db_path)

    # Создание таблиц синхронно
    table_creator.create_tables_sync()

    # В FastAPI можно вызвать `await table_creator.create_tables_async()`
