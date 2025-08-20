from typing import Any, Dict, List, Union

from models.provider_client import WorkerThread
from functions import extract_json_to_dict
from logger import Logger, read_filter, LOGGER_CONFIG


class LLMTaskRunner:
    """
    Универсальный исполнитель фоновых LLM-задач.

    Позволяет асинхронно запускать любую задачу через WorkerThread,
    используя произвольный промпт, модель и входной запрос.
    Результат обрабатывается через глобальную функцию `get_filter_response_llm`
    и логируется.

    Если задача не была запущена (start не вызван), метод finish()
    безопасно возвращает пустой список — без ошибок.

    Подходит для любых сценариев: извлечение сущностей, классификация,
    генерация фильтров, парсинг дат и т.д. — всё, что определено в промпте.
    """

    def __init__(
        self,
        query: str = "",
        prompt_name: str = "",
        model: str = "",
        addition: str = "",
        timer_label: str = "LLM Task Execution",
        logger_config: Dict = LOGGER_CONFIG,
    ) -> None:
        """
        Инициализирует исполнителя LLM-задачи.

        Args:
            query: Входной текстовый запрос.
            prompt_name: Имя промпта, определяющего задачу (например, 'extract_dates', 'classify_intent').
            model: Модель для вызова (например, 'gpt-4.1-mini').
            addition: Дополнение к запросу
            timer_label: Название для таймера в логах.
            logger_config: Конфигурация логгера. Если None — используется LOGGER_CONFIG.
        """
        self.query = query
        self.addition = addition
        self.prompt_name = prompt_name
        self.model = model
        self.timer_label = timer_label
        self.logger_config = logger_config

        self.logger_thread = None
        self.thread = None
        self._started = False
        self._finished = False

    def start(self) -> 'LLMTaskRunner':
        """
        Запускает LLM-задачу в фоновом потоке.

        Создаёт и запускает WorkerThread с указанными параметрами,
        начинает таймер и логирует входные данные.

        Returns:
            Self — для поддержки чейнинга: runner.start().finish()

        Raises:
            RuntimeError: Если задача уже запущена.
        """
        if self._started:
            raise RuntimeError("Задача уже запущена. Повторный вызов start() запрещён.")
        self._started = True

        self.logger_thread = Logger(**self.logger_config)
        self.thread = WorkerThread(
            prompt_name=self.prompt_name,
            query=self.query,
            model=self.model,
            addition=self.addition,
        )

        # Логирование начала
        self.logger_thread.add_separator(type_sep=2)
        self.logger_thread.timer_start(self.timer_label)
        self.logger_thread.add_text(f"Модель: {self.model}")
        self.logger_thread.add_text(f"Промпт: {self.prompt_name}")
        self.logger_thread.add_text(f"Запрос: {self.query}")
        self.logger_thread.output()

        self.thread.start()
        return self

    def finish(self) -> Union[List[Any], Dict[str, Any], Any]:
        """
        Завершает выполнение задачи и возвращает обработанный результат.

        Если задача не была запущена (start не вызван или поток не создан),
        возвращает пустой список `[]` — без ошибок.

        В противном случае:
        - Дожидается завершения потока,
        - Передаёт результат в `get_filter_response_llm`,
        - Логирует ответ модели и передаёт данные.

        Returns:
            Результат обработки `get_filter_response_llm(thread.result)`.
            Может быть:
                - list — например, список найденных сущностей,
                - dict — структурированный ответ,

            Если задача не запускалась — возвращает `[]`.
        """
        if self._finished:
            raise RuntimeError("Метод finish() уже был вызван.")
        self._finished = True

        # Если задача не запускалась — возвращаем пустой результат
        if not self._started or self.thread is None or self.logger_thread is None:
            return []

        self.thread.join()

        # Обработка результата — может вернуть list, dict
        result = extract_json_to_dict(self.thread.result)

        # Логируем ответ модели
        self.logger_thread.add_separator(type_sep=2)
        self.logger_thread.timer_stop(self.timer_label)  # Останавливаем таймер
        self.logger_thread.add_text("Ответ модели:")
        if not result:
            self.logger_thread.add_text("Нет ответа")
        self.logger_thread.output()

        # Логируем в общий логгер (предполагаем, что это структурированные данные)
        if isinstance(result, list):
            for item in result:
                self.logger_thread.add_json_answer(item)
                self.logger_thread.add_separator(type_sep=3)
                self.logger_thread.output(console=True, file=True)  # только в файл
                # self.logger_thread.add_json_answer(*read_filter(item))
                # self.logger_thread.output(console=True, file=False)  # только в консоль
        elif isinstance(result, dict):
            self.logger_thread.add_json_answer(result)
            self.logger_thread.output(console=True, file=True)
            # self.logger_thread.add_json_answer(read_filter(result))
            # self.logger_thread.output(console=True, file=False)

        return result