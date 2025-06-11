import asyncio
import openai
from typing import Optional
from datetime import datetime
from langsmith import traceable
from langsmith.wrappers import wrap_openai


class OpenAIClient:
    """
    Асинхронный клиент для работы с OpenAI API.

    Позволяет:
    - Менять модель OpenAI (например, "gpt-4", "gpt-3.5-turbo").
    - Настраивать системный промпт.
    - Выполнять запросы к OpenAI API асинхронно, чтобы не блокировать FastAPI.

    Атрибуты:
        api_key (str): API-ключ для доступа к OpenAI.
        model (str): Текущая используемая модель (по умолчанию "gpt-4").
        system_prompt (str): Системный промпт, задающий контекст чата.
    """

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        """
        Инициализация OpenAI клиента.

        Args:
            api_key (str): API-ключ OpenAI.
            model (str, optional): Название модели (по умолчанию "gpt-4.1").
        """
        self.model = model
        self.system_prompt = ""
        self.user_base_prompt = ""
        # self.client = openai.OpenAI(api_key=api_key)
        self.client = wrap_openai(openai.OpenAI(api_key=api_key))

        # Словарь с русскими названиями дней недели
        self.days_of_week_ru = {
            0: 'Пн',  # Понедельник
            1: 'Вт',  # Вторник
            2: 'Ср',  # Среда
            3: 'Чт',  # Четверг
            4: 'Пт',  # Пятница
            5: 'Сб',  # Суббота
            6: 'Вс'  # Воскресенье
        }

    def set_model(self, model_name: str) -> None:
        """
        Изменяет используемую модель OpenAI.

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
        now = datetime.now()
        # Форматирование даты в формат dd.mm.yyyy
        date = now.strftime("%d.%m.%Y")
        # Форматирование времени в формат HH:MM:SS
        time = now.strftime("%H:%M:%S")
        # Получение дня недели (0 - понедельник, 6 - воскресенье)
        weekday = now.weekday()

        """Читает файл и разделяет system и user промпты."""
        with open("prompts/" + query_prompt + ".txt", "r", encoding="utf-8") as f:
            content = f.read().split("---")  # Разделяем system и user по "---"

            self.system_prompt = content[0].replace("SYSTEM:\n", "").strip()

            # Добавляем дату и время
            self.user_base_prompt = f"Сейчас: {date} {time} {self.days_of_week_ru[weekday]}\n"
            self.user_base_prompt += content[1].replace("USER:\n", "").strip()

        # Добавляем метаданные
        with open("prompts/metadata_list.txt", "r", encoding="utf-8") as f:
            text = f.read()

        metadata_list = ", ".join([item.strip() for item in text.split(",") if item.strip()])
        self.user_base_prompt = self.user_base_prompt.replace("<metadata list>", metadata_list)

    @traceable
    def chat_sync(self, user_message: str) -> Optional[str]:
        """
        Синхронный вызов OpenAI API.

        Args:
            user_message (str): Текст пользовательского сообщения.

        Returns:
            Optional[str]: Ответ от OpenAI, либо None в случае ошибки.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": self.user_base_prompt + user_message}
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
