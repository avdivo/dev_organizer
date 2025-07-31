import os
import re
import time
import openai
import asyncio
import threading
from typing import Optional
from dotenv import load_dotenv
from langsmith import traceable
from langsmith.wrappers import wrap_openai

from services import get_current_time_and_weekday

# Выбор провайдера модели
# Загрузка переменных окружения
load_dotenv()

# PROVIDER_URL = "https://api.openai.com/v1"
# key_name = "OPENAI_API_KEY"
PROVIDER_URL = "https://api.cometapi.com/v1"
key_name = "COMETAPI_KEY"
MODEL_PROVIDER_KEY = os.getenv(key_name)


class AIClient:
    """
    Асинхронный клиент для работы с провайдером модели через API.

    Позволяет:
    - Менять модель (например, "gpt-4", "gpt-3.5-turbo").
    - Настраивать системный промпт.
    - Выполнять запросы к API асинхронно, чтобы не блокировать FastAPI.

    Атрибуты:
        model (str): Текущая используемая модель (по умолчанию "gpt-4").
        system_prompt (str): Системный промпт, задающий контекст чата.
    """

    def __init__(self, model: str = "gpt-4.1-mini"):
        """
        Инициализация OpenAI клиента.

        Args:
            model (str, optional): Название модели (по умолчанию "gpt-4.1").
        """
        self.model = model
        self.system_prompt = ""
        self.user_base_prompt = ""
        # self.client = openai.OpenAI(api_key=api_key)
        # self.client = wrap_openai(openai.OpenAI(api_key=api_key))

        # Создаём клиент с указанием CometAPI
        raw_client = openai.OpenAI(
            api_key=MODEL_PROVIDER_KEY,
            base_url=PROVIDER_URL
        )

        # Оборачиваем его для трассировки через LangSmith
        self.client = wrap_openai(raw_client)

    def set_model(self, model_name: str) -> None:
        """
        Изменяет используемую модель.

        Args:
            model_name (str): Название новой модели (например, "gpt-3.5-turbo").
        """
        self.model = model_name

    def load_prompt(self, query_prompt: str) -> None:
        """
        Загрузка промптов.

        Args:
            query_prompt (str): имя файла который содержит промпты для запроса.
        """
        # Получение сегодняшней даты и времени
        iso_time, weekday_name = get_current_time_and_weekday()
        # Имя файла с промптом
        prompt_name = "prompts/" + query_prompt + ".txt"

        """Читает файл и разделяет system и user промпты."""
        with open(prompt_name, "r", encoding="utf-8") as f:
            content = f.read().split("---")  # Разделяем system и user по "---"

            # Извлекаем и сохраняем системную часть промпта
            self.system_prompt = content[0].replace("SYSTEM:\n", "").strip()
            content = content[1].replace("USER:\n", "").strip()  # И User часть

            # Шаблон: всё между <- и ->
            pattern = r"<-([^<>]+)->"
            matches = re.findall(pattern, content)

            base_dir = os.path.dirname(prompt_name)

            for match in matches:
                replacement_file = os.path.join(base_dir, f"{match}.txt")
                if os.path.exists(replacement_file):
                    with open(replacement_file, 'r', encoding='utf-8') as rf:
                        replacement_text = rf.read().strip()
                        replacement_block = f"\n{replacement_text}\n"
                        content = content.replace(f"<-{match}->", replacement_block)
                else:
                    print(f"⚠️ Файл вставки в промпт не найден: {replacement_file}")

            # Добавляем дату и время в User часть промпта
            self.user_base_prompt = f"Сейчас: {iso_time} {weekday_name}\n\n"

            # Добавляем USER часть промпта со вставками
            self.user_base_prompt += content


    @traceable
    def chat_sync(self, user_message: str, addition: str = "") -> Optional[str]:
        """
        Синхронный вызов OpenAI API.

        Args:
            user_message (str): Текст пользовательского сообщения.
            addition (str): Динамические дополнения записываются вначале
        Returns:
            Optional[str]: Ответ от OpenAI, либо None в случае ошибки.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"{addition}\n\n{self.user_base_prompt}\n{user_message}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Ошибка запроса к OpenAI: {e}")
            return None

    async def chat(self, user_message: str) -> Optional[str]:
        """
        Асинхронный вызов OpenAI API (выполняется в отдельном потоке).

        Args:
            user_message (str): Текст пользовательского сообщения.

        Returns:
            Optional[str]: Ответ от OpenAI, либо None в случае ошибки.
        """
        return await asyncio.to_thread(self.chat_sync, user_message)


class WorkerThread(threading.Thread):
    """
    Поток для обработки запроса к модели.

    Args:
        create_note (str): Название промпта для загрузки.
        query (str): Запрос для модели.
        model (str): Название модели.


    Attributes:
        result (Optional[str]): Результат запроса после выполнения потока.
    """

    def __init__(self, prompt_name: str, query: str, model: str = "gpt-4.1-mini"):
        super().__init__()
        print("✅ Инициализация клиента провайдера модели")
        self.openai_client: AIClient = AIClient()  # Создаем объект
        self.prompt_name: str = prompt_name
        self.query: str = query
        self.model = model
        self.result: Optional[str] = None  # Здесь будет результат после выполнения

    def run(self) -> None:
        """Запускает обработку запроса в модели и записывает результат."""
        print("✅ Запуск потока")
        start = time.time()
        self.openai_client.load_prompt(self.prompt_name)  # Загружаем промпт
        self.openai_client.set_model(self.model)
        self.result = self.openai_client.chat_sync(" " + self.query)  # Получаем ответ
        print("Запрос в потоке выполнялся", time.time() - start)

# ✅ Запуск нескольких потоков и ожидание их завершения
# openai_client = OpenAIClient()
# requests = [
#     ("create_note", "Первый запрос"),
#     ("create_note", "Второй запрос"),
# ]
#
# threads = [WorkerThread(openai_client, create_note, query) for create_note, query in requests]
#
# for thread in threads:
#     thread.start()
#
# for thread in threads:
#     thread.join()
#
# results = [thread.result for thread in threads]
# print(results)  # ['Ответ 1', 'Ответ 2']
