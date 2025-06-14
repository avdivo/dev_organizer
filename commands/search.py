import re
import time

from openai_client import WorkerThread
from user import user
from config import embedding_db, openai_client, OPENAI_API_KEY
from functions import extract_json_to_dict, transform_filters, get_filter_response_llm


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
        thread = WorkerThread(api_key=OPENAI_API_KEY, prompt_name="search_filter", query=query, model="gpt-4.1-mini")
        thread.start()
        print("Сразу после запуска в потоке:", time.time() - start)

    # Запрос к LLM
    openai_client.load_prompt("search")  # Загрузка промпта
    openai_client.set_model("gpt-4.1")  # gpt-4.1-mini
    answer = openai_client.chat_sync(" " + query)
    if not answer:
        return "Задание провалено, ИИ не ответил. Повторите запрос."

    try:
        answer_dict = extract_json_to_dict(answer)  # Преобразуем основной ответ в dict
    except:
        return "Задание провалено, ИИ сказал что то не то. Повторите запрос."

    print(answer)
    if is_metadata:
        thread.join()  # Ожидаем завершения потока с поиском метаданных
        print(thread.result)
        add_filter = get_filter_response_llm(thread.result)  # Получаем список фильтров метаданных
    else:
        add_filter = []

    # Подготовка фильтров
    print("После обработки", answer_dict)
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
    print("После функции", filters)

    if search in ["semantic", "aggregate"] :
        # Поиск по смыслу с фильтрами
        answer = ", ".join(embedding_db.get_notes(query_text=question, filter_metadata=filters))

        # Запрос к LLM
        openai_client.load_prompt("semantic")  # Загрузка промпта
        openai_client.set_model("gpt-4.1-nano")  # gpt-4.1-mini
        answer = openai_client.chat_sync(f"\n Заметки для ответа:\n{answer}\n\nВопрос: {question}")

        return answer

    else:
        # Поиск по фильтрам
        query = {"filter_metadata": filters, "get_metadata": True}
        if where_document:
            query["word_for_search"] = {"$contains": where_document}

        answer = embedding_db.get_notes(**query)  # Получение записей из БД
        if "aggregate" not in search:
            answer = ", ".join([item["text"] for item in answer])
            return f"Ответ: {answer}"

    # Агрегирующие функции
    comment = "Запрос успешно выполнен"
    args = search.split()
    if 2 > len(args) > 3:
        return f"Ответ: {answer}"

    func_list = ["sum", "avg", "min", "max", "count"]
    func = args[1] if args[1] in func_list else "sum"

    with open("prompts/metadata_list.txt", "r", encoding="utf-8") as f:
        text = f.read()

    # Разделение и очистка
    metadata_list = [item.strip() for item in text.split(",") if item.strip()]

    try:
        field = args[2]  # Определяем поле
        if field not in metadata_list:
            comment = "Поле не опознано, если данных не будет, возможно оно ошибочное.\n"
    except:
        field = "рубли"  # Поле по умолчанию

    # Получаем нужные данные из метаданных записей
    values = []
    for item in answer:
        value = item.get("metadata", {}).get(field, None)
        if value is None:
            continue
        try:
            value = float(value)
            values.append(value)
        except ValueError:
            continue

    res = 0
    if not len(values):
        comment += "Подходящих записей не найдено"
    else:
        if func == func_list[0]:
            # Сумма
            res = sum(values)
        elif func == func_list[1]:
            # Среднее
            res = sum(values) / len(values)
        elif func == func_list[2]:
            # Минимальное
            res = min(values)
        elif func == func_list[3]:
            # Максимальное
            res = max(values)
        elif func == func_list[4]:
            # Количество
            res = len(values)
    res = int(res) if res.is_integer() else res

    # Формируем ответ
    query = (f"Вопрос: {question}\n\n "
             f"По {len(values)} записям, включи это значение в ответ\n"
             f"Результат: {res}\n"
             f"Если по контексту ответа не понятно что считаем, включи: {field} \n "
             f"Уточни, в каком списке: {list_name if list_name else 'все'}"
             f"\n{comment}")

    # Запрос к LLM
    openai_client.load_prompt("aggregate")  # Загрузка промпта
    answer = openai_client.chat_sync("\n" + query)

    return answer








