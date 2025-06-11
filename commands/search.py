from user import user
from config import embedding_db, openai_client
from functions import extract_json_to_dict, transform_filters


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

    # Запрос к LLM
    openai_client.load_prompt("search")  # Загрузка промпта
    answer = openai_client.chat_sync(" " + query)
    if not answer:
        return "Задание провалено, ИИ не ответил. Повторите запрос."

    print("До обработки", answer)
    answer_dict = extract_json_to_dict(answer)  # Преобразуем json в dict
    print("После обработки", answer_dict)
    filters = answer_dict.get("filters", [])
    search = answer_dict.get("search", "semantic")  # Способ поиска
    where_document = answer_dict.get("where_document", "")  # Поиск слова в документе
    print("До функции", filters)
    filters = transform_filters(filters)  # Преобразуем даты в timestamp и названия полей
    if list_name:
        filters.append({"list_name": {"$eq": list_name}})  # Добавляем список в фильтры
    filters.append({"user": {"$eq": str(user.id)}})  # Добавляем список в фильтры
    print("После функции", filters)
    if len(filters) > 1:
        filters = {"$and": filters}
    else:
        filters = filters[0]

    if search == "semantic":
        # Поиск по смыслу с фильтрами
        answer = ", ".join(embedding_db.get_notes(query_text=question, filter_metadata=filters))
        return f"Ответ по смыслу: {answer}"
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

    try:
        field = args[2]  # Определяем поле
        if field not in ["price", "quantity", "rating", "number"]:
            field = "price"
            comment = "Поле не опознано, по умолчанию посчитано для цен"
    except:
        field = "price"  # Поле по умолчанию

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
        comment = "Подходящих записей не найдено"
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
             f"Поле только если по контексту ответа не понятно, говори по русски: {field} \n "
             f"Уточни, в каком списке: {list_name if list_name else 'все'}"
             f"\n{comment}")

    # Запрос к LLM
    openai_client.load_prompt("aggregate")  # Загрузка промпта
    answer = openai_client.chat_sync("\n" + query)

    return answer








