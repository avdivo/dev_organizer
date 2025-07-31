import re
import time

from user import user
from config import embedding_db, provider_client, DEFAULT_LIST
from functions import extract_json_to_dict, iso_timestamp_converter, get_metadata_response_llm
from services import get_current_time_and_weekday
from errors import QueryEmptyError, ModelAnswerError

def create_note(answer: dict) -> str:
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
        bool: str Строка ответа
    """
    query = answer.get("query")  # Получаем запрос
    # Если запрос пустой нужно попросить повторить
    if not query:
        raise QueryEmptyError()

    list_name = answer.get("list_name")
    # Если целевой список не указан, сохраняем в список по умолчанию
    if not list_name:
        list_name = DEFAULT_LIST

    print("Обработка в llm запросов на добавление заметок")
    start = time.time()

    print("Запуск основного запроса:", time.time() - start)
    provider_client.load_prompt("create_note")  # Загрузка промпта
    provider_client.set_model("gpt-4.1-mini")  # gpt-4.1-mini
    answer = provider_client.chat_sync(" " + query, addition=f"Имеются списки:\n{user.get_list_str()}")
    print("Ответ LLM:\n", answer)

    if not answer:
        raise ModelAnswerError("Нет ответа.")

    try:
        notes = extract_json_to_dict(answer)  # Преобразуем ответ в list
        if not notes:
            raise
        print("Основной ответ:", notes)
        print("Сразу после отработки основного запроса:", time.time() - start)
    except:
        raise ModelAnswerError("Ошибка обработки ответа.")

    # Добавляем метаданные в заметки
    print("Перед добавлением метаданных:", time.time() - start)
    documents = []
    metadatas_new = []
    for note in notes:
        if not note:
            continue

        # Подготовка метаданных
        datetime_create = note.get("datetime_create", get_current_time_and_weekday(0))  # Дата создания
        timestamp_create = iso_timestamp_converter(datetime_create)  # Пытаемся преобразовать
        if not timestamp_create:
            # LLM может не правильно создать дату
            datetime_create = get_current_time_and_weekday(0)
            timestamp_create = iso_timestamp_converter(datetime_create)
        metadata = dict(datetime_create = datetime_create, timestamp_create=timestamp_create)

        metadata["user"] = str(user.id)  # Добавляем пользователя
        metadata["list_name"] = list_name  # Добавляем название списка
        metadata["completed"] = False  # Добавляем признак удаления
        metadata.update(get_metadata_response_llm(note.get("numbers", {})))  # Метаданные от LLM
        metadatas_new.append(metadata)

        # Подготовка текстовой части (документа)
        text = note["text"] if note.get("text", "") else query  # Документ заменяем на text от модели
        documents.append(text)

    embedding_db.add_text(documents, metadatas_new)  # Добавляем заметки в базу
    print("Документы:", documents)
    print("Метаданные:", metadatas_new)
    print("Время обработки запросов в llm", time.time() - start)

    return "Добавлено: " + ", ".join(documents)




# запиши что поездка в турцию стоит 1000 долларов а в египет 1200
# купить квас молоко 2 пакета коробка конфет
# запиши рецепт взять 2 сахара 3 молока и 1 литр кефира и смешать все а потом варить 1 час
# запиши Включив компьютер, пользователь открыл редактор, создал документ, написал текст, проверил орфографию, сохранил файл, заархивировал его и отправил по электронной почте коллеге для согласования.
# купить сметану и воду
# сегодня потратили 20 рублей а вчера 25
# запиши в заметку что завтра в 6 вечера будет футбол на слуцком стадионе