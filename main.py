import os
import time
import json

from user import user
from commands import *
from config import openai_client, LANGSMITH_API_KEY, DEFAULT_LIST, scheduler


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

# Запуск APScheduler
if not scheduler.running:
    scheduler.start()

print("\nДля завершения ввести 0\n")

while True:
    # Имитация входа в Алису. Загружаем пользователя
    user.load_by_alice_id(alice_id="12345678")

    # Выводим информацию
    print(user.name, user.lists)  # Теперь объект заполнен данными!

    user_input = input("Команда: ")
    start_time = time.time()

    if user_input == '0':
        break


    openai_client.load_prompt("query_parser")  # Загрузка промпта
    openai_client.set_model("gpt-4.1-mini")

    user_message = user_input + f"\n\nИмеющиеся списки:\n{[list_name for list_name in user.lists]}\n\n"

    answer = openai_client.chat_sync(user_message)
    openai_client.set_model("gpt-4.1")
    print(answer)
    try:
        matadata = json.loads(answer)
        action = matadata.get("action")

        # ----------------------------- Создание списка -----------------------------
        if action == "create_list":

            answer = create_list(matadata)
            print(answer)

        # ----------------------------- Создание заметки ---------------------------
        elif action == "create_note":
            if create_note(matadata):
                print("Заметка сохранена.")
            else:
                print("Заметка не создана. Повторите запрос.")

        # ----------------------------- Создание напоминания ---------------------------
        elif action == "create_reminder":
            answer = create_reminder(matadata)
            print(answer)

        # ----------------------------- Поиск ---------------------------
        elif action == "search":
            answer = search(answer=matadata, question=user_input)
            print(answer)

        else:
            print(answer)

    except Exception as e:
        raise
        print("Ошибка обработки ответа модели", e)

    print(f'---------------------{time.time() - start_time}----------------------\n')
