import os
import json
from dateparser.search import search_dates

from user import user
from commands import *
from logger import logger
from config import provider_client, LANGSMITH_API_KEY, DEFAULT_LIST, scheduler
from errors import QueryEmptyError, ModelAnswerError

os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = "dev_organizer"
os.environ["LANGCHAIN_TRACING_V2"] = "true"

# Имитация загрузки системы. Создание пользователя. Создание списка по умолчанию "заметка"
user.add_user("Алексей", telegram_id="12345678", alice_id="12345678")  # Создаем или получаем пользователя
create_list({"action": "create_list", "list_name": DEFAULT_LIST})  # Создание списка

# Запуск APScheduler
if not scheduler.running:
    scheduler.start()

print("\nДля завершения ввести 0\n")

while True:
    # Имитация входа в Алису. Загружаем пользователя
    user.load_by_alice_id(alice_id="12345678")

    # Выводим информацию
    print(f"\n{user.name}\n{user.get_list_str()}")  # Теперь объект заполнен данными!

    user_input = input("Запрос: ")
    logger.timer_start("Общее время")

    if user_input == '0':
        break
    if not user_input:
        continue

    user_message = user_input

    provider_client.load_prompt("query_parser")  # Загрузка промпта
    # Выбор модели, слабые модели плохо работают с датами,
    # поэтому используем модель посильнее
    if search_dates(user_message):
        model = "gpt-4.1"  # gpt-3.5-turbo gpt-4.1-mini
    else:
        model = "gpt-4.1-mini"
    provider_client.set_model(model)  # Выбор модели

    # Логирование только в файл
    logger.add_text("\n")
    logger.add_separator(type_sep=1)
    logger.add_text(f"Запрос: {user_message}")  # Модель и промпт
    logger.output(console=False)  # Вывод сообщения в файл

    # Логирование
    logger.add_separator(type_sep=1)
    logger.timer_start("Определение намерения")
    logger.add_text(provider_client.report())  # Модель и промпт

    answer = provider_client.chat_sync(
        user_message,
        addition=f"Списки (папки) в них записываются заметки:\n{user.get_list_str()}")
    try:
        # matadata = {'action': 'create_note', 'list_name': 'заметка', 'query': user_input}
        matadata = json.loads(answer)
        action = matadata.get("action")
        list_name = matadata.get("list_name", "")

        # Логирование результата
        logger.add_separator(type_sep=2)
        logger.add_text("Ответ модели:")
        logger.add_json_answer(matadata)
        logger.timer_stop("Определение намерения")
        logger.output()

        # Проверяем название списка, если оно есть, но отсутствует
        # в списках пользователя и это не создание списка - отменяем выполнение
        if list_name and list_name not in user.get_list_str() and action != "create_list":
            logger.add_separator(type_sep=1)
            logger.timer_stop("Общее время")
            logger.add_separator(type_sep=1)
            logger.output()
            print("Нет указанного списка.\n")
            continue

        # ----------------------------- Создание списка -----------------------------
        if action == "create_list":

            answer = create_list(matadata)

        # ----------------------------- Создание заметки ---------------------------
        elif action == "create_note":
            try:
                answer = create_note(matadata)
            except (QueryEmptyError, ModelAnswerError) as e:
                answer = e

        # ----------------------------- Создание напоминания ---------------------------
        elif action == "create_reminder":
            try:
                answer = create_reminder(matadata, question=user_input)
            except (QueryEmptyError, ModelAnswerError) as e:
                answer = str(e)

        # ----------------------------- Поиск ---------------------------
        elif action == "search":
            try:
                answer = search_manager(answer=matadata, question=user_input)
            except (QueryEmptyError, ModelAnswerError) as e:
                print(e)
                # answer = str(e)

    except Exception as e:
        raise
        print("Ошибка обработки ответа модели", e)

    logger.add_separator(type_sep=1)
    logger.add_text("Ответ:")
    logger.add_text(answer)
    logger.add_separator(type_sep=1)
    logger.timer_stop("Общее время")
    logger.add_separator(type_sep=1)
    logger.output()

    print(answer)
