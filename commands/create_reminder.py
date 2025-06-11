from user import user
from config import embedding_db, openai_client, DEFAULT_LIST
from functions import (extract_json_to_dict, generate_job_id,
                       register_job, iso_timestamp_converter)


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

    # Разбираем запрос, выбираем из него метаданные
    openai_client.load_prompt("create_reminder")  # Загрузка промпта
    answer = openai_client.chat_sync(" " + query)
    if not answer:
        return "Задание провалено, ИИ соврал. Повторите запрос."
    print(answer)
    try:
        reminder_list = extract_json_to_dict(answer)  # Преобразуем ответ в list

        answer_list = []
        for reminder in reminder_list:
            try:
                metadata = reminder.get("metadata", None)  # Метаданные
                job = reminder.get("APScheduler", None)  # Задания для планировщика
                if not metadata or not job:
                    continue
                metadata["list_name"] = list_name  # Добавляем название списка
                metadata["completed"] = False  # Добавляем признак удаления
                job_id = generate_job_id()  # Генерируем уникальный идентификатор задания
                metadata["job_id"] = job_id  # Записываем идентификатор в метаданные
                text = metadata["text"] if metadata.get("text", "") else query  # Документ заменяем на text от модели
                metadata["timestamp_create"] = iso_timestamp_converter(metadata["datetime_create"])  # timestamp даты
                metadata["timestamp_reminder"] = iso_timestamp_converter(
                    metadata["datetime_reminder"])  # timestamp даты
                metadata["user"] = str(user.id)  # Добавляем пользователя
                embedding_db.add_text([text], [metadata])  # Добавляем заметки в базу
                register_job(job_id, text, job)  # Ставим задачу напоминание
                answer_list.append(reminder.get("answer", "Напоминание сохранено"))
            except:
                print("Ошибка --------------------------------")
                continue  # В случае ошибки пропускаем задание

    except Exception as e:
        raise
        print("Ошибка обработки ответа модели", e)
        return ""

    return ", ".join(answer_list)

# напоминай мне каждый понедельник в 7 часов утра что сегодня вечером в 6 часов в бассейн
# подсказывай мне по субботам у нас гимнастика
# после завтра напомни утром побриться
# напоминай каждый месяц 19 числа проверять счет
# начиная с августа напоминай по первым понедельникам месяца переводы
# напоминай о дне рождения явтошука андрея 03.06
#  напомни завтра и послезавтра утром сходить на почту
