import re

from sympy.polys.polyconfig import query

from user import user
from logger import logger, Logger, read_filter, LOGGER_CONFIG
from models.provider_client import WorkerThread
from config import embedding_db, provider_client
from errors import QueryEmptyError, ModelAnswerError
from models.llm_task_runner import LLMTaskRunner
from functions import (extract_json_to_dict, transform_filters,
                       get_filter_response_llm)


def search_manager(answer: dict, question: str = "") -> str:
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
    # Обработка запроса ------------------------------------------

    query = answer.get("query")  # Получаем запрос
    # Если запрос пустой нужно попросить повторить
    if not query:
        raise QueryEmptyError()

    list_name = answer.get("list_name", "")  # Получаем название списка

    # Определяем наличие в тексте цифр и если они есть, запускаем параллельно
    # модель для нахождения метаданных в тексте
    is_metadata = True if bool(re.search(r'\d', query)) else False
    if is_metadata:
        # Запуск модели поиска метаданных
        searcher_metadata = LLMTaskRunner(query, "search_filter", "gpt-4.1-mini", timer_label="Поиск метаданных")
        searcher_metadata.start()

    # Запуск модели парсинга поискового запроса
    searcher_parser = LLMTaskRunner(
        query=query,
        prompt_name="search",
        model="gpt-4.1",
        addition=f"Имеющиеся списки (папки):\n{user.get_list_str()}",
        timer_label="Анализ поискового запроса")
    # Запускаем анализ и тут же ожидание ответа и получаем ответ
    answer_dict = searcher_parser.start().finish()

    # Получаем ответ парсера метаданных если он был запущен
    add_filter = []
    if is_metadata:
        add_filter = searcher_metadata.finish()

    # print(f"""
    # Вернуть список:     {answer_dict.get("need_filter", 0)}
    # О списках:          {answer_dict.get("query_is_about_lists", 0)}
    # Количество:         {answer_dict.get("need_count", 0)}
    # Умный поиск:        {answer_dict.get("semantic", 0)}
    # Ответ через модель: {answer_dict.get("need_analysis", 0)}
    # Арифметика:         {answer_dict.get("need_calculation", 0)}
    # """)
    # return ""

    # Определяем сложность запроса для выбора модели
    complex = answer_dict.get("complex", 2.0)
    model = "gpt-4.1-mini"
    try:
        if complex < 1:
            model = "gpt-4.1-nano"
        elif complex > 2:
            model = "gpt-4.1"
    except:
        pass

    # Подготовка фильтров ---------------------------------------

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

    filters = transform_filters(filters)  # Преобразуем даты в timestamp и названия полей
    if list_name:
        filters.append({"list_name": {"$eq": list_name}})  # Добавляем список в фильтры

    filters.append({"user": {"$eq": str(user.id)}})  # Добавляем пользователя в фильтры
    if len(filters) > 1:
        filters = {"$and": filters}
    else:
        filters = filters[0]

    # Выбор метода и поиск данных ----------------------------------------------
    # Алгоритм см. /docs/search_method_select.md

    where_document = answer_dict.get("where_document", "")  # Поиск слова в документе
    semantic = answer_dict.get("semantic", 0)
    need_calculation = answer_dict.get("need_calculation", 0)
    query_is_about_lists = answer_dict.get("query_is_about_lists", 0)
    need_count = answer_dict.get("need_count", 0)
    need_analysis = answer_dict.get("need_analysis", 0)
    need_filter = answer_dict.get("need_filter", 0)

    logger_title = None
    logger_title = "Ответ после фильтра"  # Логирование
    answer = None

    # 1 Семантический поиск
    if semantic:
        need_analysis = 1

        essence = answer_dict.get("essence", question)  # Суть поисковой фразы
        # Поиск по смыслу с фильтрами
        answer = embedding_db.get_notes_semantic(query_text=essence, filter_metadata=filters)
        logger_title = "Ответ после семантического поиска"  # Логирование

    # 2 Фильтр по слову или фразе
    if where_document:
        need_filter = 1

        if semantic:
            answer = [
                item for item in answer
                if where_document.lower() not in item["page_content"].lower()
            ]

    # 3 Нужно выполнить арифметические действия
    if need_calculation:
        need_analysis = 1
        semantic = 0

    # 4 Поиск в БД с применением фильтров
    if not semantic and (need_analysis or need_filter):
        # Поиск по фильтрам
        query = {"filter_metadata": filters}
        if where_document:
            query["word_for_search"] = {"$contains": where_document.lower()}
        answer = embedding_db.get_notes_filter(**query)  # Получение записей из БД

    # 5 Вопросы по спискам/папкам
    if query_is_about_lists:
        need_analysis = 1

    # 6 Нужно посчитать количество записей
    if need_count:
        if not need_analysis:
            if answer is None:
                return "Ничего нет"
            return f"Количество: {len(answer)}"
        if answer is not None:
            answer = f"Количество записей/заметок: {len(answer)}\n\n{answer}"

    # 7 Получение ответа от модели (аналитика)
    if need_analysis:
        # Запуск модели для ответа
        answer = LLMTaskRunner(
            query=f"\n{answer}\n\nВопрос: {question}",
            prompt_name="llm_smart",
            model=model,
            addition=f"Имеющиеся списки (папки):\n{", ".join(user.get_list_str())}",
            timer_label=logger_title)
        # Запускаем анализ и тут же ожидание ответа и получаем ответ
        answer = answer.start().finish()

        out = "Возникла ошибка, ответ не получен."
        try:
            out = eval("f'" + answer.get("text", out) + "'")
        except:
            pass
        return out

    # 8 Вывод записей без обработки
    if need_filter:
        item_list = [item["page_content"] for item in answer]
        if not item_list: return "Нет данных"
        return ',\n'.join(item for item in item_list)

    # 9 Ответа нет
    return "Ответа нет"


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
        dict: ответ можно посмотреть в промпте search.txt
    """

    query = answer.get("query")
    # Определяем наличие в тексте цифр и если они есть, запускаем параллельно
    # модель для нахождения метаданных в тексте
    is_metadata = True if bool(re.search(r'\d', query)) else False
    if is_metadata:
        # В потоке запускаем поиск метаданных в запросе
        logger_thread = Logger(**LOGGER_CONFIG)  # Создаем экземпляр логера
        prompt_name = "search_filter"
        model = "gpt-4.1-mini"
        thread = WorkerThread(prompt_name=prompt_name, query=query, model=model)

        # Логирование
        logger_thread.add_separator(type_sep=3)
        logger_thread.timer_start("Поиск метаданных")
        logger_thread.add_text(f"Модель: {model}, Промпт: {prompt_name}")
        logger_thread.add_text(f"Запрос: {query}")

        thread.start()

    # Запрос к LLM
    provider_client.load_prompt("search")  # Загрузка промпта
    provider_client.set_model("gpt-4.1")  # gpt-4.1-mini

    # Логирование
    logger.add_separator(type_sep=2)
    logger.timer_start("Поиск")
    logger.add_text(provider_client.report())  # Модель и промпт
    logger.add_text(f"Запрос: {query}")
    logger.output()

    answer = provider_client.chat_sync(" " + query, addition=f"Имеющиеся списки (папки):\n{user.get_list_str()}")
    if not answer:
        raise ModelAnswerError("Нет ответа..")


    answer_dict = extract_json_to_dict(answer)  # Преобразуем основной ответ в dict
    if not answer_dict:
        raise ModelAnswerError("Ошибка обработки основного ответа.")

    # Логирование результата
    logger.add_separator(type_sep=2)
    logger.add_text("Ответ модели:")
    logger.add_json_answer(answer_dict)
    logger.timer_stop("Поиск")
    logger.output()

    if is_metadata:
        thread.join()  # Ожидаем завершения потока с поиском метаданных

        # Логирование ответа модели
        add_filter = get_filter_response_llm(thread.result)  # Получаем список фильтров метаданных
        logger_thread.add_separator(type_sep=3)
        logger_thread.add_text("Ответ модели:")
        logger_thread.output()

        # Логирование результата в разные места
        for filter in add_filter:
            logger.add_json_answer(filter)
            logger.output(console=False)  # только в файл
            logger.add_json_answer(*read_filter(filter))
            logger.output(file=False)  # только в консоль
        logger_thread.timer_stop("Поиск метаданных")
        logger_thread.output()
    else:
        add_filter = []
    print(f"""
    Вернуть список:     {answer_dict.get("need_filter", 0)}
    О списках:          {answer_dict.get("query_is_about_lists", 0)}
    Количество:         {answer_dict.get("need_count", 0)}
    Умный поиск:        {answer_dict.get("semantic", 0)}
    Ответ через модель: {answer_dict.get("need_analysis", 0)}
    Арифметика:         {answer_dict.get("need_calculation", 0)}
    """)
    return ""






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

    # Определяем сложность запроса для выбора модели
    complex = answer_dict.get("complex", 2.0)
    model = "gpt-4.1-mini"
    try:
        if complex < 1:
            model = "gpt-4.1-nano"
        elif complex > 2:
            model = "gpt-4.1"
    except:
        pass
    provider_client.set_model(model)

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

    logger_title = None
    if search == "semantic" :
        essence = answer_dict.get("essence", question)  # Суть поисковой фразы
        # Поиск по смыслу с фильтрами
        answer = embedding_db.get_notes_semantic(query_text=essence, filter_metadata=filters)
        logger_title = "Модель после семантического поиска"  # Логирование


        # Запрос к модели
        # provider_client.load_prompt("semantic")  # Загрузка промпта
        provider_client.load_prompt("llm_smart")  # Загрузка промпта
        # provider_client.set_model(model)  # gpt-4.1-mini

    else:
        # Поиск по фильтрам
        query = {"filter_metadata": filters}
        if where_document:
            query["word_for_search"] = {"$contains": where_document.lower()}

        answer = embedding_db.get_notes_filter(**query)  # Получение записей из БД

    if search == "filter":
        # Логирование
        logger.add_separator(type_sep=2)
        logger.timer_start("Ответ после фильтра из БД")
        return ',\n'.join(item["page_content"] for item in answer)
    elif search == "llm_smart":
        provider_client.load_prompt("llm_smart")  # Загрузка промпта
        # provider_client.set_model("gpt-4.1-mini")  # gpt-4.1-mini
        logger_title = "Модель после фильтра"  # Логирование

    # Логирование
    logger.add_separator(type_sep=2)
    logger.timer_start(logger_title)
    logger.add_text(provider_client.report())  # Модель и промпт
    logger.add_text(f"В запросе: ответ БД и вопрос: {question}")
    logger.output()

    answer = provider_client.chat_sync(f"\n{answer}\n\nВопрос: {question}", addition=f"Имеющиеся списки (папки):\n{user.get_list_str()}")

    # Логирование результата
    logger.add_separator(type_sep=2)
    logger.add_text("Ответ модели:")
    logger.add_json_answer(answer)
    logger.timer_stop(logger_title)
    logger.output()

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
