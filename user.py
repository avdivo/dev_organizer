from typing import Optional, Dict, Any
from config import sql_db  # Импорт клиента БД
from errors import UserNotFoundError

class User:
    """
    Класс, представляющий пользователя в системе.
    Позволяет добавлять, загружать и управлять данными пользователя.

    Атрибуты:
        id (Optional[int]): Уникальный идентификатор пользователя.
        name (Optional[str]): Имя пользователя.
        telegram_id (Optional[str]): Идентификатор Telegram.
        alice_id (Optional[str]): Идентификатор Алисы.
        created_at (Optional[str]): Дата создания записи.
        lists (Dict[str, str]): Связанные списки пользователя {list_name: config}.
        db_client (SQLiteClient): Подключение к SQLite-клиенту для работы с БД.
    """

    def __init__(self) -> None:
        """
        Создаёт пустой объект пользователя.
        Данные загружаются позже через `add_user()` или `load_by_alice_id()`.
        """
        self.id: Optional[int] = None
        self.name: Optional[str] = None
        self.telegram_id: Optional[str] = None
        self.alice_id: Optional[str] = None
        self.created_at: Optional[str] = None
        self.lists: Dict[str, str] = {}  # Списки пользователя
        self.db_client = sql_db  # Подключение к БД

    def add_user(self, name: str, telegram_id: Optional[str] = None, alice_id: Optional[str] = None) -> None:
        """
        Добавляет нового пользователя в базу данных (синхронно).
        Если пользователь уже существует, загружает его данные.

        Args:
            name (str): Имя пользователя.
            telegram_id (Optional[str]): Идентификатор Telegram.
            alice_id (Optional[str]): Идентификатор Алисы.

        Returns:
            None
        """
        check_query = "SELECT * FROM users WHERE telegram_id = ? OR alice_id = ?"
        existing_user = self.db_client.execute_sync(check_query, (telegram_id, alice_id))

        if existing_user:
            self.fill_data(existing_user[0])  # Заполняем объект данными из БД
            return

        insert_query = "INSERT INTO users (name, telegram_id, alice_id) VALUES (?, ?, ?)"
        self.db_client.execute_sync(insert_query, (name, telegram_id, alice_id))

        user_data = self.db_client.execute_sync(check_query, (telegram_id, alice_id))[0]
        self.fill_data(user_data)

    async def add_user_async(self, name: str, telegram_id: Optional[str] = None, alice_id: Optional[str] = None) -> None:
        """
        Асинхронно добавляет нового пользователя в базу данных.
        Если пользователь уже существует, загружает его данные.

        Args:
            name (str): Имя пользователя.
            telegram_id (Optional[str]): Идентификатор Telegram.
            alice_id (Optional[str]): Идентификатор Алисы.

        Returns:
            None
        """
        check_query = "SELECT * FROM users WHERE telegram_id = ? OR alice_id = ?"
        existing_user = await self.db_client.execute_async(check_query, (telegram_id, alice_id))

        if existing_user:
            self.fill_data(existing_user[0])  # Заполняем объект данными из БД
            return

        insert_query = "INSERT INTO users (name, telegram_id, alice_id) VALUES (?, ?, ?)"
        await self.db_client.execute_async(insert_query, (name, telegram_id, alice_id))

        user_data = (await self.db_client.execute_async(check_query, (telegram_id, alice_id)))[0]
        self.fill_data(user_data)

    def load_by_alice_id(self, alice_id: str) -> bool:
        """
        Загружает данные пользователя из базы данных по `alice_id` (синхронно).

        Args:
            alice_id (str): Идентификатор Алисы.

        Returns:
            bool: `True`, если данные загружены успешно, `False`, если пользователь не найден.
        """
        query = """
        SELECT users.*, user_lists.list_name, user_lists.config
        FROM users
        LEFT JOIN user_lists ON user_lists.user_id = users.id
        WHERE users.alice_id = ?
        """
        results = self.db_client.execute_sync(query, (alice_id,))

        if not results:
            raise UserNotFoundError(alice_id)

        self.fill_data(results[0])

        for row in results:
            if row["list_name"]:
                self.lists[row["list_name"]] = row["config"]

        return True

    async def load_by_alice_id_async(self, alice_id: str) -> bool:
        """
        Асинхронно загружает данные пользователя по `alice_id`.

        Args:
            alice_id (str): Идентификатор Алисы.

        Returns:
            bool: `True`, если данные загружены успешно, `False`, если пользователь не найден.
        """
        query = """
        SELECT users.*, user_lists.list_name, user_lists.config
        FROM users
        LEFT JOIN user_lists ON user_lists.user_id = users.id
        WHERE users.alice_id = ?
        """
        results = await self.db_client.execute_async(query, (alice_id,))

        if not results:
            return False

        self.fill_data(results[0])

        for row in results:
            if row["list_name"]:
                self.lists[row["list_name"]] = row["config"]

        return True

    def fill_data(self, data: dict) -> None:
        """
        Заполняет объект данными пользователя из БД.

        Args:
            data (dict): Словарь с данными пользователя.

        Returns:
            None
        """
        self.id = data["id"]
        self.name = data["name"]
        self.telegram_id = data["telegram_id"]
        self.alice_id = data["alice_id"]
        self.created_at = data["created_at"]

# Создаём пустой объект пользователя
user = User()
