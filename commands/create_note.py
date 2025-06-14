import re
import time

from user import user
from config import embedding_db, openai_client, DEFAULT_LIST, OPENAI_API_KEY
from functions import extract_json_to_dict, iso_timestamp_converter, get_metadata_response_llm
from openai_client import WorkerThread


def create_note(answer: dict) -> bool:
    """
    Добавляет новую заметку для текущего пользователя, в заданный список.

    Args:
        answer (dict): Ответ модели:
        {
            "action": "create_note",
            "query": "это заметка без команды создания заметки",
            "list_name": "список"
        }

    Returns:
        bool: False - сообщаем что заметка не создана, True - создана
    """
    query = answer.get("query")  # Получаем запрос
    # Если запрос пустой нужно попросить повторить
    if not query:
        return False

    list_name = answer.get("list_name")
    # Если целевой список не указан, сохраняем в список по умолчанию
    if not list_name:
        list_name = DEFAULT_LIST

    print("Обработка в llm запросов на добавление заметок")
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
    # Разбираем основной запрос, выбираем из него метаданные
    print("Запуск основного запроса:", time.time() - start)
    openai_client.load_prompt("create_note")  # Загрузка промпта
    openai_client.set_model("gpt-4.1")  # gpt-4.1-mini
    answer = openai_client.chat_sync(" " + query)

    if not answer:
        return False

    try:
        answer_list = extract_json_to_dict(answer)  # Преобразуем ответ в list
        print("Основной ответ:", answer_list)
        print("Сразу после отработки основного запроса:", time.time() - start)
    except:
        return False

    if is_metadata:
        thread.join()  # Ожидаем завершения потока с поиском метаданных
        print("После ожидания выполнения потока:", time.time() - start)
        # Разбираем запрос метаданными и объединяем его с основным
        metadata_llm = get_metadata_response_llm(thread.result)  # Получаем список дополнительных метаданных
    else:
        metadata_llm = []

    # Сохраняем заметку
    numbers = answer_list.get("numbers", [])  # Получаем список номеров числительных в тексте
    metadatas = answer_list.get("data", [])  # Список заметок
    numbers_in_metadata = [list(v.values())[0] for v in metadata_llm]  # Список номеров числительных в метаданных

    # Добавляем метаданные в заметки
    print("Перед добавлением метаданных:", time.time() - start)
    documents = []
    metadatas_new = []
    for metadata in metadatas:
        if not metadata:
            continue
        indexes = metadata.pop("numbers", [])  # Забираем индексы чисел из списка которые есть в этой заметке
        metadata["list_name"] = list_name  # Добавляем название списка
        metadata["completed"] = False  # Добавляем признак удаления
        text = metadata["text"] if metadata.get("text", "") else query  # Документ заменяем на text от модели
        documents.append(text)
        metadata["timestamp_create"] = iso_timestamp_converter(metadata.get("datetime_create", None))  # timestamp даты
        metadata["user"] = str(user.id)  # Добавляем пользователя

        # Проверяем числа на наличие категорий и добавляем в заметку как метаданные
        for index in indexes:
            try:
                number = numbers[index]  # Получаем число
                if number == numbers_in_metadata[index]:
                    metadata.update(metadata_llm[index])  # Добавляем дополнительные метаданные
            except:
                continue

        metadatas_new.append(metadata)
    embedding_db.add_text(documents, metadatas_new)  # Добавляем заметки в базу
    print("Документы:", documents)
    print("Метаданные:", metadatas_new)
    print("Время обработки запросов в llm", time.time() - start)
    return True



# запиши что поездка в турцию стоит 1000 долларов а в египет 1200
# купить квас молоко 2 пакета коробка конфет
# запиши рецепт взять 2 сахара 3 молока и 1 литр кефира и смешать все а потом варить 1 час
# запиши Включив компьютер, пользователь открыл редактор, создал документ, написал текст, проверил орфографию, сохранил файл, заархивировал его и отправил по электронной почте коллеге для согласования.
# купить сметану и воду
# сегодня потратили 20 рублей а вчера 25
# запиши в заметку что завтра в 6 вечера будет футбол на слуцком стадионе