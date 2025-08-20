from user import user
from logger import logger
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

    provider_client.load_prompt("create_note")  # Загрузка промпта
    provider_client.set_model("gpt-4.1-mini")  # gpt-4.1-mini

    # Логирование
    logger.add_separator(type_sep=2)
    logger.timer_start("Добавление заметок")
    logger.add_text(provider_client.report())  # Модель и промпт
    logger.add_text(f"Запрос: {query}")
    logger.output()

    answer = provider_client.chat_sync(" " + query,
                                       addition=f"Имеющиеся списки (папки):\n{user.get_list_str()}")

    if not answer:
        raise ModelAnswerError("Нет ответа.")
    try:
        notes = extract_json_to_dict(answer)  # Преобразуем ответ в list[dict]
        if not notes:
            raise
        # Логирование результата только в файл
        logger.add_separator(type_sep=2)
        logger.add_text("Ответ модели:")
        logger.add_json_answer(notes)
        logger.output(console=False)
        logger.add_separator(type_sep=2)
        logger.add_text("Ответ модели можно посмотреть в логе.\nСейчас может быть поиск метаданных или сразу запись в БД.")
        logger.output(file=False)

    except:
        raise ModelAnswerError("Ошибка обработки ответа.")

    # Добавляем метаданные в заметки
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
        metadata = dict(datetime_create=datetime_create, timestamp_create=timestamp_create)

        metadata["user"] = str(user.id)  # Добавляем пользователя
        metadata["list_name"] = list_name  # Добавляем название списка
        metadata["completed"] = False  # Добавляем признак удаления
        metadata.update(get_metadata_response_llm(note.get("numbers", {})))  # Метаданные от LLM
        metadatas_new.append(metadata)

        # Подготовка текстовой части (документа)
        text = note["text"] if note.get("text", "") else query  # Документ заменяем на text от модели
        documents.append(text)

    embedding_db.add_text(documents, metadatas_new)  # Добавляем заметки в базу

    # Логирование результата
    logger.add_separator(type_sep=2)
    logger.add_text("Отправка в БД")
    for doc, data in zip(documents, metadatas_new):
        logger.add_separator(type_sep=3)
        logger.add_json_answer(doc)
        logger.add_json_answer(data)
    logger.add_separator(type_sep=2)
    logger.timer_stop("Добавление заметок")
    logger.output()

    return f"В {list_name} добавлено: {", ".join(documents)}"
