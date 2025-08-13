import time

from user import user
from logger import logger
from errors import QueryEmptyError, ModelAnswerError
from config import embedding_db, provider_client, DEFAULT_LIST
from functions import (extract_json_to_dict, generate_job_id,
                       register_job, iso_timestamp_converter, get_metadata_response_llm)
from services import get_current_time_and_weekday


def create_reminder(answer: dict, question: str) -> str:
    """
    Добавляет новое напоминание для текущего пользователя, в заданный список.

    Args:
        answer (dict): Ответ модели:
        question (str): текст запроса без изменений
        {
            "action": "create_reminder",
            "query": "это заметка для создания напоминания",
            "list_name": "список"
        }

    Returns:
        bool: False - сообщаем что заметка не создана, True - создана
    """
    query = question  # Запрос без изменений
    list_name = answer.get("list_name")
    # Если целевой список не указан, сохраняем в список по умолчанию
    if not list_name:
        list_name = DEFAULT_LIST

    # Разбираем запрос, выбираем из него метаданные
    provider_client.load_prompt("create_reminder")  # Загрузка промпта
    provider_client.set_model("gpt-4.1-2025-04-14")  # gpt-4.1-mini gpt-4.1-2025-04-14

    # Логирование
    logger.add_separator(type_sep=2)
    logger.timer_start("Добавление напоминаний")
    logger.add_text(provider_client.report())  # Модель и промпт
    logger.add_text(f"Запрос: {query}")
    logger.output()

    answer = provider_client.chat_sync(" " + query)
    if not answer:
        raise ModelAnswerError("Нет ответа.")

    try:
        reminders = extract_json_to_dict(answer)  # Преобразуем ответ в list
        if not reminders:
            raise ValueError("Пустой результат")

        # Логирование результата только в файл
        logger.add_separator(type_sep=2)
        logger.add_text("Ответ модели:")
        logger.add_json_answer(reminders)
        logger.output(console=False)
        logger.add_separator(type_sep=2)
        logger.add_text("Ответ модели можно посмотреть в логе.\nСейчас может быть поиск метаданных или сразу запись в БД.")
        logger.output(file=False)

    except:
        raise ModelAnswerError("Ошибка обработки ответа.")

    # Добавляем метаданные в напоминания
    # Начало логирования результатов
    logger.add_separator(type_sep=2)
    logger.add_text("Отправка в БД")

    message_to_user = []
    for reminder in reminders:
        if not reminder:
            continue

        # Разделитель в логе
        logger.add_separator(type_sep=3)

        # Получение основных частей напоминания
        data = reminder.get("data", {})  # Получаем данные заметки
        job = reminder.get("APScheduler", None)  # Задания для планировщика

        # Проверка правильности напоминания
        if not data or not job:
            answer = reminder.get("answer", "Ошибка в напоминании")  # Ответ пользователю
            logger.add_text(f"Ответ пользователю: {answer}")  # Добавление в лог
            message_to_user.append(answer)
            continue

        # Подготовка метаданных
        date_reminder = data.get("datetime_reminder", None)  # Дата напоминания
        timestamp_reminder = iso_timestamp_converter(date_reminder)  # Пытаемся преобразовать
        if not timestamp_reminder:
            answer = "Ошибка при обработке дат."  # Ответ пользователю
            logger.add_text(f"Ответ пользователю: {answer}")  # Добавление в лог
            message_to_user.append(answer)
            continue

        # Убеждаемся, что дата не прошла. Модель может ошибаться.
        datetime_now = get_current_time_and_weekday(0)
        timestamp_now = iso_timestamp_converter(datetime_now)
        if timestamp_now >= timestamp_reminder:
            logger.add_text(f"Ответ пользователю: эта дата прошла.")  # Добавление в лог
            message_to_user.append("эта дата прошла")
            continue

        metadata = dict(date_reminder = date_reminder, timestamp_reminder=timestamp_reminder)

        # Проверка и запись дат начала и окончания напоминаний
        start_date = job.get("start_date", None)  # Дата первого напоминания
        timestamp_start_date = iso_timestamp_converter(start_date)  # Пытаемся преобразовать
        if timestamp_start_date:
            metadata["start_date"] = start_date
            metadata["timestamp_start_date"] = timestamp_start_date

        end_date = job.get("end_date", None)  # Дата завершения напоминаний
        timestamp_end_date = iso_timestamp_converter(end_date)  # Пытаемся преобразовать
        if timestamp_end_date:
            metadata["end_date"] = end_date
            metadata["timestamp_end_date"] = timestamp_end_date

        datetime_create = data.get("datetime_create", get_current_time_and_weekday(0))  # Дата создания
        timestamp_create = iso_timestamp_converter(datetime_create)  # Пытаемся преобразовать
        if not timestamp_create:
            # LLM может не правильно создать дату
            datetime_create = get_current_time_and_weekday(0)
            timestamp_create = iso_timestamp_converter(datetime_create)
        metadata["datetime_create"] = datetime_create
        metadata["timestamp_create"] = timestamp_create

        # Подготовка текстовой части (документа). При сработке напоминания
        text = data["text"] if data.get("text", "") else query  # Документ заменяем на text от модели

        try:
            trigger = job.get("trigger", None)  # Получаем триггер (способ оповещения)
            metadata["trigger"] = trigger
            job_id = generate_job_id()  # Генерируем уникальный идентификатор задания
            metadata["job_id"] = job_id  # Записываем идентификатор в метаданные
            register_job(job_id, text, job)  # Ставим задачу напоминание

        except:
            logger.add_text(f"Ответ пользователю: ошибка установки таймера")  # Добавление в лог
            message_to_user.append("ошибка установки таймера")
            continue

        answer = reminder.get("answer", "Напоминание сохранено")  # Ответ пользователю
        message_to_user.append(answer)
        logger.add_text(f"Ответ пользователю: {answer}")  # Добавление в лог
        logger.add_text(f"Сообщение при сработке напоминания: {text}")  # Добавление в лог

        metadata["user"] = str(user.id)  # Добавляем пользователя
        metadata["list_name"] = list_name  # Добавляем название списка
        metadata["completed"] = False  # Добавляем признак удаления
        metadata.update(get_metadata_response_llm(data.get("numbers", {})))  # Метаданные от LLM

        embedding_db.add_text([text], [metadata])  # Добавляем заметки в базу

        logger.add_json_answer(metadata)
        logger.add_separator(type_sep=3)
        logger.add_text("В APScheduler:")  # Добавление в лог
        logger.add_json_answer(job)

    # Завершение логирования результата
    logger.add_separator(type_sep=2)
    logger.timer_stop("Добавление напоминаний")
    logger.output()

    return ", ".join(message_to_user)
