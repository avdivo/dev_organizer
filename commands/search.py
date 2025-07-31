import re
import time

from provider_client import WorkerThread
from user import user
from config import embedding_db, provider_client
from functions import (extract_json_to_dict, transform_filters,
                       get_filter_response_llm)


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
    answer = provider_client.chat_sync(" " + query, addition=f"Имеются списки:\n{user.get_list_str()}")
    if not answer:
        return "Задание провалено, ИИ не ответил. Повторите запрос."

    try:
        answer_dict = extract_json_to_dict(answer)  # Преобразуем основной ответ в dict
    except:
        return "Задание провалено, ИИ сказал что то не то. Повторите запрос."

    print("Основной запрос поиска:\n", answer, "\n")

    if is_metadata:
        thread.join()  # Ожидаем завершения потока с поиском метаданных
        print("Уточнение метаданных для поиска:\n", thread.result, "\n")
        add_filter = get_filter_response_llm(thread.result)  # Получаем список фильтров метаданных
    else:
        add_filter = []

    # Подготовка фильтров
    # Получаем фильтры дат и добавляем к ним фильтры других метаданных
    f = answer_dict.get("filters", [])
    # выбираем только нужные поля
    filters = add_filter
    try:
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

    if search == "semantic" :
        essence = answer_dict.get("essence", question)  # Суть поисковой фразы
        # Поиск по смыслу с фильтрами
        answer = embedding_db.get_notes_semantic(query_text=essence, filter_metadata=filters)

        # Запрос к модели
        # provider_client.load_prompt("semantic")  # Загрузка промпта
        provider_client.load_prompt("llm_smart")  # Загрузка промпта
        provider_client.set_model("gpt-4.1-mini")  # gpt-4.1-mini

    else:
        # Поиск по фильтрам
        query = {"filter_metadata": filters}
        if where_document:
            query["word_for_search"] = {"$contains": where_document.lower()}

        answer = embedding_db.get_notes_filter(**query)  # Получение записей из БД

    if search == "filter":
        return ',\n'.join(item["page_content"] for item in answer)
    elif search == "llm_smart":
        provider_client.load_prompt("llm_smart")  # Загрузка промпта
        provider_client.set_model("gpt-4.1-mini")  # gpt-4.1-mini
    # elif search == "llm_lite":
    #     provider_client.load_prompt("llm_lite")  # Загрузка промпта
    #     provider_client.set_model("gpt-4.1-nano")  # gpt-4.1-mini

    answer = provider_client.chat_sync(f"\n{answer}\n\nВопрос: {question}", addition=f"Имеются списки:\n{user.get_list_str()}")

    try:
        out = eval("f'" + answer + "'")
    except:
        out = "Задание провалено, ошибка модели. Повторите запрос.\n" + answer
    return out

# добавь список кладовка
# добавь в кладовку лобзик на 1 полку
# добавь в кладовку дрель на 1 полку
# добавь в кладовку ручной инструмент на 2 полку
# добавь в кладовку крепеж на 3 полку
# добавь в кладовку электрику на 4 полку

# filter:
# что на полке номер два
# что на второй полке
# что в кладовке

# llm_smart:
# cколько полок в кладовке
# на какой полке больше всего предметов

# semantic:
# электроинструмент есть в кладовке
# где в кладовке шурупы
# где гвозди
