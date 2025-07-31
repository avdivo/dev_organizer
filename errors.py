class UserError(Exception):
    """Базовый класс для ошибок, связанных с пользователем."""
    pass

class UserNotFoundError(UserError):
    """Ошибка: Пользователь не найден в системе."""
    def __init__(self, alice_id: str):
        super().__init__(f"⚠️ Пользователь alice_id '{alice_id}' не найден.")

class AuthorizationError(UserError):
    """Ошибка: Неправильные учетные данные или недостаточно прав."""
    def __init__(self, message: str = "⚠️ Ошибка авторизации: Доступ запрещен."):
        super().__init__(message)

class QueryError(Exception):
    """Базовый класс для ошибок, связанных с запросами."""
    pass

class QueryEmptyError(QueryError):
    """Пустой запрос."""
    def __init__(self):
        super().__init__(f"⚠️ Пустой запрос.")

class ModelError(Exception):
    """Базовый класс для ошибок, связанных с моделями."""
    pass

class ModelAnswerError(ModelError):
    """Неправильный ответ модели."""
    def __init__(self, message: str):
        super().__init__(f"⚠️ Модель вернула некорректный ответ. {message}")