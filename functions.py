import re
import json
import time
import uuid
from user import user
from typing import Dict, List, Any, Union, Optional
from apscheduler.job import Job
from ast import literal_eval
from jobs import reminder_job
from config import scheduler
from datetime import datetime, timezone
from dateutil import parser

def check_metadata(metadata: dict) -> dict:
    """
    Уточнение и корректировка метаданных найденных моделями
      {
        "text": факт 1 (обязательное поле)
        "price": сумма/цена,
        "datetime_create": создания заметки (обязательное поле)
        "quantity": количество
        "number": номер или цифра которую нельзя отнести к имеющимся
        "rating": рейтинг
        "scheduled_datetime":  если заметка предполагает напоминание записать начало
    }
    Args:
        metadata (dict): словарь с метаданными от модели

    Returns:
        dict: уточненный словарь
    """
    list_keys = ["text", "price", "datetime_create", "quantity", "number", "rating",
                 "list_name", "datetime_reminder"]
    out = {}
    for key in list_keys:
        if key in metadata and metadata[key] != "":
            out[key] = metadata[key]
    out["user"] = str(user.id)  # Добавляем пользователя

    return out


# def convert_to_chroma_filter(data: Dict[str, str]) -> Union[Dict[str, Any], None]:
#     """
#     Преобразует словарь с фильтрами в формат ChromaDB с автоматическим преобразованием чисел.
#
#     :param data: Словарь, где ключи — поля, а значения могут содержать операторы (> , < , = , <= , >=).
#     :return: Корректный фильтр для ChromaDB.
#     """
#     chroma_conditions = []
#
#     operator_mapping = {
#         "=": "$eq",
#         ">": "$gt",
#         "<": "$lt",
#         ">=": "$gte",
#         "<=": "$lte",
#     }
#
#     for key, value in data.items():
#         if not value:  # Пропускаем пустые значения
#             continue
#
#         match = re.match(r"^(>=|<=|>|<|=)?\s*(.+)$", value)
#         if match:
#             operator, real_value = match.groups()
#             if not operator:
#                 operator = "="  # Если оператор отсутствует, считаем его равенством
#
#             # Попытка преобразования числа (если возможно)
#             try:
#                 if key != "user":
#                     # id пользователя оставляем строчным
#                     real_value = float(real_value) if "." in real_value else int(real_value)
#             except ValueError:
#                 pass  # Оставляем как строку, если не число
#
#             chroma_conditions.append({key: {operator_mapping[operator]: real_value}})
#
#     # 🔹 Убираем "$and", если только одно условие (чтобы избежать ошибки ChromaDB)
#     if not chroma_conditions:
#         return None
#     elif len(chroma_conditions) == 1:
#         return chroma_conditions[0]
#     else:
#         return {"$and": chroma_conditions}
#

def extract_json_to_dict(text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """
    Извлекает JSON-словарь или список из строки и возвращает его как объект Python.
    Корректно обрабатывает вложенные структуры и находит точные границы JSON.

    Args:
        text: Строка, содержащая JSON-данные (может быть окружена другим текстом)

    Returns:
        Union[Dict[str, Any], List[Any], None]:
        - Распарсенный словарь или список Python
        - None, если JSON не найден/невалиден

    """
    # Улучшенный шаблон для словарей и списков
    pattern = r'''
        (?P<dict>\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})|  # Словари
        (?P<list>\[(?:[^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\])  # Списки
    '''

    for match in re.finditer(pattern, text, re.VERBOSE):
        json_str = match.group()
        try:
            # Пробуем распарсить как JSON (с обработкой одинарных кавычек)
            json_str = json_str.replace("'", '"')  # Заменяем одинарные кавычки
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # Безопасная альтернатива eval
                result = literal_eval(json_str)
                if isinstance(result, (dict, list)):
                    return result
            except (ValueError, SyntaxError):
                continue

    return None


def generate_job_id():
    return f"job_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def register_job(job_id: str, message: str, job_dict: Dict) -> Job:
    """
    Регистрирует задание в планировщике APScheduler на основе словаря параметров.

    :param job_id: Уникальный идентификатор задания.
    :param message: сообщение
    :param job_dict: Словарь параметров задания, включая ключ 'trigger' и параметры для соответствующего триггера.
    :return: Объект созданного задания (Job).
    """
    job_dict = job_dict.copy()  # чтобы не модифицировать оригинальный словарь
    trigger_type = job_dict.pop("trigger")
    job = scheduler.add_job(
        func=reminder_job,
        trigger=trigger_type,
        id=job_id,
        kwargs={"job_id": job_id, "message": message},
        **job_dict
    )
    print(f"Создано задание с ID: {job.id}")
    return job


def extract_and_parse_json():
    ...
def iso_timestamp_converter(value: Union[str, int]) -> Union[int, str]:
    """
    Конвертирует между ISO 8601 и UNIX timestamp в UTC.

    - Если вход — строка ISO 8601 (с или без часового пояса), возвращает timestamp (int) UTC.
      Если часовой пояс не указан, считается, что время в UTC.
    - Если вход — timestamp (int), возвращает ISO 8601 строку в UTC с суффиксом 'Z'.

    :param value: str или int
    :return: int или str
    """
    if isinstance(value, str):
        dt = parser.isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return int(dt.timestamp())

    elif isinstance(value, int):
        dt = datetime.fromtimestamp(value, timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')


    else:
        raise ValueError("Аргумент должен быть строкой ISO 8601 или целым числом (timestamp)")


def transform_filters(filters: list) -> list:
    """
    Трансформирует список условий, заменяя названия полей по `field_mapper()`
    и конвертируя значения в `timestamp`, если поле меняется.

    Args:
        filters (list): Список условий, например:
            [
                {"datetime_create": {"$gte": "2025-06-09T00:00:00"}},
                {"datetime_create": {"$lte": "2025-06-09T23:59:59"}}
            ]

    Returns:
        list: Обновлённые условия с заменёнными полями и конвертированными значениями.
    """
    field_map = {
        "datetime_create": "timestamp_create",
        "datetime_reminder": "timestamp_reminder",
    }

    transformed = []
    for condition in filters:
        field, value = next(iter(condition.items()))
        if field in field_map:
            field = field_map[field]
            key, date = next(iter(value.items()))
            value = {key: iso_timestamp_converter(date)}
        transformed.append({field: value})

    return transformed