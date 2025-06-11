from config import sql_db
from user import user


def create_list(answer: dict) -> str:
    """
    Добавляет новый список для текущего пользователя, если такого ещё нет.

    Args:
        answer (dict): Ответ модели:
        {
            "action": "create_list",
            "list_name": "кладовка"
            "config": в данный момент не передается, служит для расширения функционала
        }

    Returns:
        str: Сообщение
    """
    try:
        list_name = answer["list_name"]
        list_config = answer.get("config", "")

        # Проверяем, существует ли список у пользователя
        check_query = "SELECT id FROM user_lists WHERE user_id = ? AND list_name = ?"
        existing_list = sql_db.execute_sync(check_query, (user.id, list_name))

        if existing_list:
            return f"⚠️ Список '{list_name}' уже существует."

        # Создаём новый список
        insert_query = "INSERT INTO user_lists (user_id, list_name, config) VALUES (?, ?, ?)"
        sql_db.execute_sync(insert_query, (user.id, list_name, list_config))
        return f"✅ Список '{list_name}' создан."

    except Exception as e:
        raise Exception("Ошибка добавления списка", e)
