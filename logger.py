from time import time
import json
from datetime import datetime


LOGGER_CONFIG = {}  # "console":False, "file":False

class Logger:
    def __init__(self,
                 console: bool = True,
                 file: bool = True,
                 filename: str = "log.log"):
        """
        Регистрация событий и их входных/выходных данных,
        а так же времени работы

        :param console: Вывод в консоль
        :param file: Вывод в файл
        :param filename: Имя файла лога
        """
        self.console = console
        self.file = file
        self.filename = filename

        self.output_buffer = []
        self.timers = {}  # Таймеры {name: time_start}

    def output(self, console: bool = None, file: bool = None):
        """
        Вывод содержимого буфера в консоль и файл.
        Можно временно (только в этот раз) включить вывод.

        :param console: временно разрешить вывод в консоль
        :param file: временно разрешить вывод в файл
        """
        # Определяем разрешения на вывод
        console = self.console if console is None else console
        file = self.file if file is None else file

        if console:
            print("\n".join(self.output_buffer))

        if file:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write("\n".join(self.output_buffer) + "\n")

        self.output_buffer.clear()

    def timer_start(self, name: str):
        """
        Добавление таймера в список со временем запуска

        :param name: название таймера (подпись)
        """
        self.add_text(f"▷▷▷ {name} (Старт: {datetime.now().strftime("%H:%M:%S")})")
        self.timers[name] = time()

    def timer_stop(self, name: bool = None) -> float:
        """
        Остановка таймера и вывод результата

        :param name: название таймера (подпись)
        :return: показания таймера (сек)
        """
        if name not in self.timers:
            return 0
        result = time() - self.timers[name]
        self.add_text(f"{name}: {result}")
        del (self.timers[name])  # Удаляем таймер
        return result

    def add_separator(self, type_sep: int = 1):
        """
        Добавляет в буфер разделитель
        :param type_sep: Тип разделителя
        """
        sep = f"{'-' * 60}"
        if type_sep == 1:
            sep = f"{'=' * 60}"
        elif type_sep == 3:
            sep = f"{'-' * 40}"
        self.add_text(sep)

    def add_text(self, text: str = ""):
        """
        Добавляет в буфер текст
        :param text:
        """
        self.output_buffer.append(text)

    def add_json_answer(self, text: dict):
        """
        Добавляет в буфер текст
        :param text:
        """
        self.add_text(json.dumps(text, indent=4, sort_keys=True, ensure_ascii=False))


print("✅ Инициализация логера")
logger = Logger(**LOGGER_CONFIG)


def read_filter(filter: dict) -> list:
    """
    Расшифровка фильтра для БД.
    Возвращает список строк с выражениями.

    :param filter: фильтр ф формате Chroma
    :return: список выражений

    Примеры входных данных:
    {
        "where": {
            "user": {
                "$eq": "1"
            }
        }
    }

    {
        "where": {
            "$and": [
                {
                    "list_name": {
                        "$eq": "расход"
                    }
                },
                {
                    "user": {
                        "$eq": "1"
                    }
                }
            ]
        }
    }
    """
    out = []
    example_dict = filter.get("where", filter)
    if "$and" not in example_dict:
        example_dict = [example_dict]
    else:
        example_dict = example_dict["$and"]
    for item in example_dict:
        key, value = next(iter(item.items()))
        operator, value = next(iter(value.items()))
        if operator == "$eq":
            operator = "=="
        elif operator == "$ne":
            operator = "!="
        elif operator == "$gt":
            operator = ">"
        elif operator == "$gte":
            operator = ">="
        elif operator == "$lt":
            operator = "<"
        elif operator == "$lte":
            operator = "<="
        out.append(f"{key} {operator} {value}")

    return out
