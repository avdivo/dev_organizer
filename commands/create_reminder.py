import re
import time

from user import user
from config import embedding_db, openai_client, DEFAULT_LIST, OPENAI_API_KEY
from functions import (extract_json_to_dict, generate_job_id,
                       register_job, iso_timestamp_converter, get_metadata_response_llm)
from services import get_current_time_and_weekday


def create_reminder(answer: dict) -> str:
    """
    Добавляет новое напоминание для текущего пользователя, в заданный список.

    Args:
        answer (dict): Ответ модели:
        {
            "action": "create_reminder",
            "query": "это заметка для создания напоминания",
            "list_name": "список"
        }

    Returns:
        bool: False - сообщаем что заметка не создана, True - создана
    """
    query = answer.get("query")  # Получаем запрос
    # Если запрос пустой нужно попросить повторить
    if not query:
        return "Задание провалено, запрос пустой. Повторите запрос."

    list_name = answer.get("list_name")
    # Если целевой список не указан, сохраняем в список по умолчанию
    if not list_name:
        list_name = DEFAULT_LIST

    print("Обработка в llm запросов на добавление напоминаний")
    start = time.time()

    # Разбираем запрос, выбираем из него метаданные
    openai_client.load_prompt("create_reminder")  # Загрузка промпта
    openai_client.set_model("gpt-4.1")  # gpt-4.1-mini
    answer = openai_client.chat_sync(" " + query)
    if not answer:
        return "Задание провалено, ИИ соврал. Повторите запрос."

    try:
        reminders = extract_json_to_dict(answer)  # Преобразуем ответ в list
        if not reminders:
            raise
        print("Основной ответ:", reminders)
        print("Сразу после отработки основного запроса:", time.time() - start)
    except:
        return "Задание провалено, ИИ соврал. Повторите запрос."

    # Добавляем метаданные в заметки
    print("Перед добавлением метаданных:", time.time() - start)
    message_to_user = []
    for reminder in reminders:
        if not reminder:
            continue
        # Получение основных частей напоминания
        data = reminder.get("data", {})  # Получаем данные заметки
        job = reminder.get("APScheduler", None)  # Задания для планировщика
        answer = reminder.get("answer", "Напоминание сохранено")  # Ответ пользователю
        if not data or not job: continue

        # Подготовка текстовой части (документа)
        text = data["text"] if data.get("text", "") else query  # Документ заменяем на text от модели

        # Подготовка метаданных
        date_reminder = data.get("date_reminder", None)  # Дата напоминания
        timestamp_reminder = iso_timestamp_converter(date_reminder)  # Пытаемся преобразовать
        if not timestamp_reminder: continue
        metadata = dict(date_reminder = date_reminder, timestamp_reminder=timestamp_reminder)

        datetime_create = data.get("datetime_create", get_current_time_and_weekday(0))  # Дата создания
        timestamp_create = iso_timestamp_converter(datetime_create)  # Пытаемся преобразовать
        if not timestamp_create:
            # LLM может не правильно создать дату
            datetime_create = get_current_time_and_weekday(0)
            timestamp_create = iso_timestamp_converter(datetime_create)
        metadata["datetime_create"] = datetime_create
        metadata["timestamp_create"] = timestamp_create

        try:
            job_id = generate_job_id()  # Генерируем уникальный идентификатор задания
            metadata["job_id"] = job_id  # Записываем идентификатор в метаданные
            register_job(job_id, text, job)  # Ставим задачу напоминание
            message_to_user.append(answer)
        except:
            continue

        metadata["user"] = str(user.id)  # Добавляем пользователя
        metadata["list_name"] = list_name  # Добавляем название списка
        metadata["completed"] = False  # Добавляем признак удаления
        metadata.update(get_metadata_response_llm(data.get("numbers", {})))  # Метаданные от LLM

        print("Документы:", text)
        print("Метаданные:", metadata)
        embedding_db.add_text([text], [metadata])  # Добавляем заметки в базу

    print("Время обработки запросов в llm", time.time() - start)
    return ", ".join(message_to_user)

# напоминай мне каждый понедельник в 7 часов утра что сегодня вечером в 6 часов в бассейн
# подсказывай мне по субботам у нас гимнастика
# после завтра напомни утром побриться
# напоминай каждый месяц 19 числа проверять счет
# начиная с августа напоминай по первым понедельникам месяца переводы
# напоминай о дне рождения явтошука андрея 03.06
#  напомни завтра и послезавтра утром сходить на почту
# напоминай каждый месяц 19 числа пополнить счет на 100 рублей
# напомни что на следующей неделе 18 числа нужно проехать 20 километров за 3 часа со скоростью 16
