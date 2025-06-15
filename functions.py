import re
import json
import time
import uuid
from typing import Dict, List, Any, Union, Optional, Tuple
from apscheduler.job import Job
from ast import literal_eval
from jobs import reminder_job
from config import scheduler, embedding_db
from datetime import datetime, timezone
from dateutil import parser


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


def iso_timestamp_converter(value: Union[str, int, None]) -> Union[int, str]:
    """
    Конвертирует между ISO 8601 и UNIX timestamp в UTC.

    - Если вход — строка ISO 8601 (с или без часового пояса), возвращает timestamp (int) UTC.
      Если часовой пояс не указан, считается, что время в UTC.
    - Если вход — timestamp (int), возвращает ISO 8601 строку в UTC с суффиксом 'Z'.

    :param value: str или int
    :return: int или str
    """
    if value is None:
        return 0

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


def get_metadata_response_llm(response: str) -> List[Dict]:
    """
    :param response:
    :return: List - список словарей с метаданными [{field_name: volume}, ...]
    """
    try:
        answer_list = extract_json_to_dict(response)  # Получаем ответ с метаданными от llm
    except:
        return []
    filters = {"system": {"$eq": "metadata_list"}}
    out = []
    for imem in answer_list:
        d, text = next(iter(imem.items()))  # Число и его категория (определенная ИИ)
        # print("\nЗапрос:", d, text)
        # Запрос к БД
        answer = embedding_db.get_notes(query_text=text,
                                        filter_metadata=filters, k=1, get_metadata=True)
        # print("Выбрать отсюда:", answer)
        # print(f'{answer[0]["metadata"]["ids"]} = {d}')
        print("Из БД:", answer)
        if not answer: continue
        metadata_field = answer[0].get("metadata", {}).get("ids")  # Получаем название поля
        if not metadata_field: continue
        out.append({metadata_field: d})

    return out


def get_filter_response_llm(response: str) -> List[Dict]:
    """
    :param response:
    :return: List - список словарей с метаданными [{"рубль, валюта": {"$gt": 5}}, ...]
    """
    try:
        answer_list = extract_json_to_dict(response)  # Получаем ответ с метаданными от llm
    except:
        return []
    print(answer_list)
    filters = {"system": {"$eq": "metadata_list"}}
    out = []
    for imem in answer_list:
        text, f = next(iter(imem.items()))  # Категория (определенная ИИ) и фильтр

        # Запрос к БД
        answer = embedding_db.get_notes(query_text=text,
                                        filter_metadata=filters, k=1, get_metadata=True)

        if not answer: continue
        metadata_field = answer[0].get("metadata", {}).get("ids")  # Получаем название поля
        if not metadata_field: continue
        out.append({metadata_field: f})

    return out


def simplify_notes_for_llm(raw_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Преобразует список заметок в упрощённый формат, удобный для обработки моделью.

    Оставляет только поля: "datetime_create", "text", "list_name", "completed", "datetime_reminder".
    Все поля извлекаются через .get(), чтобы избежать KeyError при отсутствии.

    :param raw_notes: Список заметок в исходной вложенной структуре
    :return: Список заметок в упрощённом виде
    """
    simplified = []
    for item in raw_notes:
        metadata = item.get("metadata", {})
        simplified.append({
            "datetime_create": metadata.get("datetime_create"),
            "text": metadata.get("text"),
            "list_name": metadata.get("list_name"),
            "completed": metadata.get("completed"),
            "datetime_reminder": metadata.get("datetime_reminder")  # может быть None
        })
    return simplified
