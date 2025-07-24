import re
import time

from provider_client import WorkerThread
from user import user
from config import embedding_db, provider_client
from functions import (extract_json_to_dict, transform_filters,
                       get_filter_response_llm, simplify_notes_for_llm)


def search(answer: dict, question: str = "") -> str:
    """
    :argument: answer (dict): Ответ модели:
        {
            "action": что сделать,
            "query": запрос, очищенный от команды,
            "list_name": название списка из списка ниже, если он указан
        }
    :argument: оригинальный запрос пользователя

    :return:
        str: ответ
    """
    query = answer.get("query")  # Получаем запрос
    # Если запрос пустой нужно попросить повторить
    if not query:
        return "Задание провалено, запрос пустой. Повторите запрос."

    list_name = answer.get("list_name", "")  # Получаем название списка

    start = time.time()
    # Определяем наличие в тексте цифр и если они есть, запускаем параллельно
    # промпт для нахождения метаданных в тексте
    is_metadata = True if bool(re.search(r'\d', query)) else False

    if is_metadata:
        # В потоке запускаем поиск метаданных в запросе
        print("Запуск в потоке:", time.time() - start)
        thread = WorkerThread(prompt_name="search_filter", query=query, model="gpt-4.1-mini")
        thread.start()
        print("Сразу после запуска в потоке:", time.time() - start)

    # Запрос к LLM
    provider_client.load_prompt("search")  # Загрузка промпта
    provider_client.set_model("gpt-4.1")  # gpt-4.1-mini
    answer = provider_client.chat_sync(" " + query)
    if not answer:
        return "Задание провалено, ИИ не ответил. Повторите запрос."

    try:
        answer_dict = extract_json_to_dict(answer)  # Преобразуем основной ответ в dict
    except:
        return "Задание провалено, ИИ сказал что то не то. Повторите запрос."

    print("Основной запрос поиска:\n", answer, "\n")

    if is_metadata:
        thread.join()  # Ожидаем завершения потока с поиском метаданных
        print("Выборка метаданных для поиска:\n", thread.result, "\n")
        add_filter = get_filter_response_llm(thread.result)  # Получаем список фильтров метаданных
    else:
        add_filter = []

    # Подготовка фильтров
    # Получаем фильтры дат и добавляем к ним фильтры других метаданных
    f = answer_dict.get("filters", [])
    # выбираем только нужные поля
    try:
        filters = add_filter
        for item in f:
            field, f = next(iter(item.items()))
            if field in ["datetime_reminder", "datetime_create"]:
                filters.append(item)
    except:
        pass

    search = answer_dict.get("search", "semantic")  # Способ поиска
    where_document = answer_dict.get("where_document", "")  # Поиск слова в документе
    filters = transform_filters(filters)  # Преобразуем даты в timestamp и названия полей
    if list_name:
        filters.append({"list_name": {"$eq": list_name}})  # Добавляем список в фильтры
    filters.append({"user": {"$eq": str(user.id)}})  # Добавляем пользователя в фильтры
    if len(filters) > 1:
        filters = {"$and": filters}
    else:
        filters = filters[0]

    print("Фильтры\n", filters, "\n")

    if search == "semantic_and_llm" :
        essence = answer_dict.get("essence", question)  # Суть поисковой фразы
        # Поиск по смыслу с фильтрами
        answer = embedding_db.get_notes(query_text=essence, filter_metadata=filters, get_metadata=True)
        simplify_answer = simplify_notes_for_llm(answer)

        # Запрос к модели
        provider_client.load_prompt("simple_answer")  # Загрузка промпта
        provider_client.set_model("gpt-4.1-nano")  # gpt-4.1-mini
        answer = provider_client.chat_sync(f"\n{simplify_answer}\n\nВопрос: {question}")

        return answer

    else:
        # Поиск по фильтрам
        query = {"filter_metadata": filters, "get_metadata": False if search == "filter" else True}
        if where_document:
            query["word_for_search"] = {"$contains": where_document}

        answer = embedding_db.get_notes(**query)  # Получение записей из БД

        if search == "filter":
            return ', '.join(text for text in answer)

        # Запрос к LLM
        if search == "llm_smart":
            provider_client.load_prompt("semantic")  # Загрузка промпта
            provider_client.set_model("gpt-4.1-mini")  # gpt-4.1-mini
        else:
            provider_client.load_prompt("simple_answer")  # Загрузка промпта
            provider_client.set_model("gpt-4.1-nano")  # gpt-4.1-mini

        simplify_answer = simplify_notes_for_llm(answer)
        answer = provider_client.chat_sync(f"\n{simplify_answer}\n\nВопрос: {question}")

        try:
            out = eval("f'" + answer + "'")
        except:
            out = "Задание провалено, ошибка модели. Повторите запрос.\n" + answer
        return out





