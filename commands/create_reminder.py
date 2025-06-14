import re
import time

from user import user
from config import embedding_db, openai_client, DEFAULT_LIST, OPENAI_API_KEY
from functions import (extract_json_to_dict, generate_job_id,
                       register_job, iso_timestamp_converter, get_metadata_response_llm)
from openai_client import WorkerThread


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

    # Определяем наличие в тексте цифр и если они есть, запускаем параллельно
    # промпт для нахождения метаданных в тексте
    is_metadata = True if bool(re.search(r'\d', query)) else False

    if is_metadata:
        # В потоке запускаем поиск метаданных в запросе
        print("Запуск в потоке:", time.time() - start)
        thread = WorkerThread(api_key=OPENAI_API_KEY, prompt_name="get_metadata", query=query, model="gpt-4.1-mini")
        thread.start()
        print("Сразу после запуска в потоке:", time.time() - start)

    # Разбираем запрос, выбираем из него метаданные
    openai_client.load_prompt("create_reminder")  # Загрузка промпта
    openai_client.set_model("gpt-4.1")  # gpt-4.1-mini
    answer = openai_client.chat_sync(" " + query)
    if not answer:
        return "Задание провалено, ИИ соврал. Повторите запрос."

    try:
        answer_list = extract_json_to_dict(answer)  # Преобразуем ответ в list
    except:
        return "Задание провалено, ИИ соврал. Повторите запрос."

    if is_metadata:
        thread.join()  # Ожидаем завершения потока с поиском метаданных
        print("После ожидания выполнения потока:", time.time() - start)
        # Разбираем запрос метаданными и объединяем его с основным
        metadata_llm = get_metadata_response_llm(thread.result)  # Получаем список дополнительных метаданных
    else:
        metadata_llm = []

    # Сохраняем заметку
    numbers = answer_list.get("numbers", [])  # Получаем список номеров числительных в тексте
    reminders = answer_list.get("reminders", [])  # Список заметок
    numbers_in_metadata = [list(v.values())[0] for v in metadata_llm]  # Список номеров числительных в метаданных

    # Добавляем метаданные в заметки
    print("Перед добавлением метаданных:", time.time() - start)
    to_user = []
    for reminder in reminders:
        job = reminder.get("APScheduler", None)  # Задания для планировщика
        metadata = reminder.pop("data", {})  # Получаем данные заметки
        if not metadata or not job:
            continue
        indexes = metadata.pop("numbers", [])  # Забираем индексы чисел из списка которые есть в этой заметке
        metadata["list_name"] = list_name  # Добавляем название списка
        metadata["completed"] = False  # Добавляем признак удаления
        text = metadata["text"] if metadata.get("text", "") else query  # Документ заменяем на text от модели
        metadata["timestamp_create"] = iso_timestamp_converter(metadata.get("datetime_create", None))  # timestamp даты
        metadata["timestamp_reminder"] = iso_timestamp_converter(metadata.get("datetime_reminder", None))  # timestamp даты
        metadata["user"] = str(user.id)  # Добавляем пользователя
        job_id = generate_job_id()  # Генерируем уникальный идентификатор задания
        metadata["job_id"] = job_id  # Записываем идентификатор в метаданные

        # Проверяем числа на наличие категорий и добавляем в заметку как метаданные
        for index in indexes:
            try:
                number = numbers[index]  # Получаем число
                if number == numbers_in_metadata[index]:
                    metadata.update(metadata_llm[index])  # Добавляем дополнительные метаданные
            except:
                continue

        # embedding_db.add_text([text], [metadata])  # Добавляем заметки в базу
        print("Документы:", text)
        print("Метаданные:", metadata)
        register_job(job_id, text, job)  # Ставим задачу напоминание
        to_user.append(reminder.get("answer", "Напоминание сохранено"))
        embedding_db.add_text([text], [metadata])  # Добавляем заметки в базу

    print("Время обработки запросов в llm", time.time() - start)

    return ", ".join(to_user)

# напоминай мне каждый понедельник в 7 часов утра что сегодня вечером в 6 часов в бассейн
# подсказывай мне по субботам у нас гимнастика
# после завтра напомни утром побриться
# напоминай каждый месяц 19 числа проверять счет
# начиная с августа напоминай по первым понедельникам месяца переводы
# напоминай о дне рождения явтошука андрея 03.06
#  напомни завтра и послезавтра утром сходить на почту
# напоминай каждый месяц 19 числа пополнить счет на 100 рублей
# напомни что на следующей неделе 18 числа нужно проехать 20 километров за 3 часа со скоростью 16
