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