from datetime import datetime
import pytz


def get_current_time_and_weekday(index: int = 2) -> tuple[str, str] or str:
    """
    Возвращает текущее время в формате ISO 8601 и день недели на русском.

    📌 Аргументы:
        - int: 0 - только дату и время, 1 - только день недели, 2 - оба в tuple,

    🔹 Возвращает:
        - str: Текущее время в формате ISO 8601 (например, "2025-06-16T07:38:00+03:00").
        - str: Название дня недели на русском (например, "Понедельник").
    """
    # Указываем часовой пояс UTC+3 (Москва)
    tz = pytz.timezone("Europe/Moscow")
    current_time = datetime.now(tz)  # Получаем текущее время

    # Форматируем в ISO 8601
    iso_time = current_time.isoformat()

    # Словарь с русскими названиями дней недели
    days_of_week_ru = {
        0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
        4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
    }

    # Определяем номер дня и его название
    weekday_name = days_of_week_ru[current_time.weekday()]

    # ЧТо вернуть
    out = iso_time, weekday_name
    if index > 1:
        return out
    return out[index]
