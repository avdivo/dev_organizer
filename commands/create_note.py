from config import embedding_db, openai_client, DEFAULT_LIST
from functions import extract_json_to_dict, check_metadata, iso_timestamp_converter


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

    # Разбираем запрос, выбираем из него метаданные
    openai_client.load_prompt("create_note")  # Загрузка промпта
    answer = openai_client.chat_sync(" " + query)
    if not answer:
        return False

    try:
        metadata_list = extract_json_to_dict(answer)  # Преобразуем ответ в list
        print(metadata_list)
        documents = []
        metadatas = []
        for metadata in metadata_list:
            metadata["list_name"] = list_name  # Добавляем название списка
            metadata = check_metadata(metadata)  # Проверяем и корректируем метаданные
            metadata["completed"] = False  # Добавляем признак удаления
            text = metadata["text"] if metadata.get("text", "") else query  # Документ заменяем на text от модели
            metadata["timestamp_create"] = iso_timestamp_converter(metadata["datetime_create"])  # timestamp даты
            documents.append(text)
            metadatas.append(metadata)
            print(f"Заметки:\n{documents}\nМетаданные:\n{metadatas}")
        embedding_db.add_text(documents, metadatas)  # Добавляем заметки в базу

    except Exception as e:
        raise
        print("Ошибка обработки ответа модели", e)
        return False

    return True
