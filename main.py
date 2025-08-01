import os
import time
import json
from dateparser.search import search_dates


from user import user
from commands import *
from config import provider_client, LANGSMITH_API_KEY, DEFAULT_LIST, scheduler
from errors import QueryEmptyError, ModelAnswerError

os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = "dev_organizer"
os.environ["LANGCHAIN_TRACING_V2"] = "true"

# Имитация загрузки системы. Создание пользователя. Создание списка по умолчанию "заметка"
user.add_user("Алексей", telegram_id="12345678", alice_id="12345678") # Создаем или получаем пользователя
create_list({"action": "create_list", "list_name": DEFAULT_LIST})  # Создание списка

"""
@app.get("/user_lists/{alice_id}")
async def get_user_lists(alice_id: str):
    lists = await sql_db.get_user_lists_by_alice_id_async(alice_id)
    return lists
"""

# -------------------------------------------------------------
# from config import embedding_db
# from functions import extract_json_to_dict
# from openai_client import OpenAIClient
#
#
# openai_client1 = OpenAIClient(api_key=OPENAI_API_KEY)
# while True:
#
#     user_input = input("Команда: ")
#     start_time = time.time()
#
#     if user_input == '0':
#         break
#
#     openai_client1.load_prompt("get_metadata")  # Загрузка промпта
#     openai_client1.set_model("gpt-4.1-mini")
#     answer_llm = openai_client1.chat_sync(f"\n{user_input}")
#     print("Ответ модели:", answer_llm)
#     answer_list = extract_json_to_dict(answer_llm)
#     filters = {"system": {"$eq": "metadata_list"}}
#     for imem in answer_list:
#         d, text = next(iter(imem.items()))
#         print("\nЗапрос:", text)
#         answer = embedding_db.get_notes(query_text=text,
#                                         filter_metadata=filters, k=1, get_metadata=True)
#         print(answer)
#         for i in answer:
#             print(f"Ответ {d}:", i)
#
#     print(f'---------------------{time.time() - start_time}----------------------\n')
# -------------------------------------------------------------
# за 3 часа мы проехали 20 киллометров со скоростью 3 киллометров в час и сделази 3 остановки последняя была на горке высотой 3 метра
# на 3 полке в кладовке 5 банок варения 3 из них малиновое и 2 клубничных
# 15 человек бросали 3 мяча и сделали 300 ударов о стену
# Запуск APScheduler
if not scheduler.running:
    scheduler.start()

print("\nДля завершения ввести 0\n")

while True:
    # Имитация входа в Алису. Загружаем пользователя
    user.load_by_alice_id(alice_id="12345678")

    # Выводим информацию
    print(f"{user.name}\n{user.get_list_str()}")  # Теперь объект заполнен данными!

    user_input = input("Команда: ")
    start_time = time.time()

    if user_input == '0':
        break
    if not user_input:
        continue

    user_message = user_input

    provider_client.load_prompt("query_parser")  # Загрузка промпта
    # Выбор модели, слабые содели плохо работают с датами,
    # поэтому используем модель посильнее
    if search_dates(user_message):
        provider_client.set_model("gpt-4.1")  #gpt-3.5-turbo gpt-4.1-mini
    else:
        provider_client.set_model("gpt-4.1-nano")

    answer = provider_client.chat_sync(
        user_message,
        addition=f"Списки (папки) в них записываются заметки:\n{user.get_list_str()}")
    provider_client.set_model("gpt-4.1-mini")
    print(answer)

    try:
        # matadata = {'action': 'create_note', 'list_name': 'заметка', 'query': user_input}
        matadata = json.loads(answer)
        action = matadata.get("action")
        list_name = matadata.get("list_name", "")

        # Проверяем название списка, если оно есть, но отсутствует
        # в списках пользователя и это не создание списка - отменяем выполнение
        if list_name and list_name not in user.get_list_str() and action != "create_list":
            print("Нет указанного списка.\n")
            continue

        # ----------------------------- Создание списка -----------------------------
        if action == "create_list":

            answer = create_list(matadata)
            print(answer)

        # ----------------------------- Создание заметки ---------------------------
        elif action == "create_note":
            try:
                answer = create_note(matadata)
            except (QueryEmptyError, ModelAnswerError) as e:
                answer = e
            print(answer)

        # ----------------------------- Создание напоминания ---------------------------
        elif action == "create_reminder":
            answer = create_reminder(matadata)
            print(answer)

        # ----------------------------- Поиск ---------------------------
        elif action == "search":
            try:
                answer = search(answer=matadata, question=user_input)
            except (QueryEmptyError, ModelAnswerError) as e:
                answer = e
            print(answer)

        else:
            print(answer)

    except Exception as e:
        raise
        print("Ошибка обработки ответа модели", e)

    print(f'---------------------{time.time() - start_time}----------------------\n')
