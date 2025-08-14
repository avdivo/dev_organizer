from typing import Dict, List, Optional, Tuple

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from logger import logger, read_filter


class EmbeddingDatabase:
    """
    Класс для управления базой данных эмбеддингов и работы с моделью эмбеддингов.

    Позволяет инициализировать базу данных, добавлять текстовые данные с метаданными и извлекать релевантные записи.
    """

    def __init__(self, persist_directory: str, model_name: str):
        """
        Инициализация базы данных эмбеддингов и модели эмбеддингов.

        :param persist_directory: Путь к директории для хранения базы данных Chroma.
        :param model_name: Название модели эмбеддингов HuggingFace.
        """
        self.embedding_model = HuggingFaceEmbeddings(model_name=model_name)
        # self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=self.embedding_model)

        documents = self.load_metadata_entries("models/prompts/metadata_list.txt")
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embedding_model,
            persist_directory=persist_directory  # Директория для сохранения [9, 12]
        )

        # print(self.vector_store._collection.get(include=["embeddings", "documents", "metadatas"]))  # Показывает всю базу

    def add_text(self, text: List[str], metadatas: List[Dict[str, str]] = None) -> None:
        """
        Добавляет текст в базу данных эмбеддингов с метаданными.

        :param text: Текст для сохранения в базе данных.
        :param metadatas: Словарь метаданных (например, {"категория": "заметки", "дата": "04.06.2025"}).
        """
        text = [note.lower() for note in text]
        metadatas = metadatas or []  # Если метаданные не переданы, создаем пустой список
        self.vector_store.add_texts(texts=text, metadatas=metadatas)  # Записываем с эмбеддингами

    def get_notes_semantic(self, query_text: Optional[str] = "",
                           filter_metadata: Optional[Dict[str, str]] = None,
                           limit: float = 1.1) -> List:
        """
        Извлекает заметки, фильтруя их по метаданным и находя похожие тексты по эмбеддингам.
        Возвращает список словарей с текстами заметок и их метаданными.

        :param query_text: Текстовый запрос для поиска похожих записей (если передан).
        :param filter_metadata: Словарь метаданных для фильтрацииФормат:
                {"ключ": {"$eq": значение}, "числовое_поле": {"$gte": число}}
        :param limit: максимальное векторное расстояние для включения записи в вывод

        :return: Список [{metadata: dict, page_content: str}]
        """
        # Логирование
        logger.add_separator(type_sep=3)
        logger.timer_start("Семантический поиск")
        logger.add_text(f"Запрос: {query_text}")
        logger.add_text(f"Фильтры:")
        logger.add_json_answer(read_filter(filter_metadata))
        logger.output(file=False)
        logger.add_json_answer(filter_metadata)
        logger.output(console=False)

        results = self.vector_store.similarity_search_with_score(query=query_text, filter=filter_metadata)

        out = [
            {"metadata": doc.metadata, "page_content": doc.page_content}
            for doc, distance in results if distance <= limit
        ]

        # Логирование результата
        logger.add_separator(type_sep=3)
        logger.timer_stop("Семантический поиск")
        logger.add_separator(type_sep=3)
        logger.add_text(f"Ответ БД:")
        logger.output()

        # Логирование результата
        for doc in out:
            logger.add_json_answer(doc)
            logger.output(console=False)  # только в файл
            logger.add_json_answer(doc["page_content"])
            logger.output(file=False)  # только в консоль

        return out

    def get_notes_filter(self, filter_metadata: Optional[Dict[str, str]] = None,
                         word_for_search: dict = None) -> List:
        """
        Извлекает заметки, фильтруя их по метаданным и ключевому слову.
        Возвращает список словарей с текстами заметок и их метаданными.

        :param query_text: Текстовый запрос для поиска похожих записей (если передан).
        :param filter_metadata: Словарь метаданных для фильтрацииФормат:
                {"ключ": {"$eq": значение}, "числовое_поле": {"$gte": число}}
        :param word_for_search: слово или фраза для поиска документов

        :return: Список [{metadata: dict, page_content: str}]
        """
        param = {"where": filter_metadata}
        if word_for_search:
            # Активация поиска документа по слову
            param["where_document"] = word_for_search

        # Логирование
        logger.add_separator(type_sep=3)
        logger.timer_start("Поиск по фильтру")
        logger.add_text(f"Фильтр:")
        logger.output()
        for item in read_filter(param):
            logger.add_text(item)
        logger.output(file=False)
        logger.add_json_answer(param)
        logger.output(console=False)

        results = self.vector_store.get(**param)

        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        # zip-уем попарно, если кол-во элементов совпадает
        out = [
            {"metadata": meta, "page_content": text}
            for text, meta in zip(documents, metadatas)
        ]

        # Логирование результата
        logger.add_separator(type_sep=3)
        logger.timer_stop("Поиск по фильтру")
        logger.add_separator(type_sep=3)
        logger.add_text(f"Ответ БД:")
        logger.output()

        # Логирование результата
        for doc in out:
            logger.add_json_answer(doc)
            logger.output(console=False)  # только в файл
            logger.add_json_answer(doc["page_content"])
            logger.output(file=False)  # только в консоль

        return out

    def load_metadata_entries(self, filepath: str) -> List:
        """
        Загружает записи метаданных из текстового файла и преобразует их в список объектов Document
        с метаданными. Формирование списка ids/

        Формат файла:
        Каждая строка должна содержать запись в формате:
            ключ: описание
        где
            ключ — уникальный идентификатор записи (например, speed_kmh),
            описание — текстовое описание единицы измерения или объекта.

        Строки, начинающиеся с '#' или пустые строки, игнорируются.

        Возвращаемое значение:
            metadata_names (list) - список ids документов
            list of Document — список документов для векторного индексирования, где
            page_content — описание,
            metadata содержит поля:
                - system: фиксированное значение "metadata_list" для фильтрации,
                - key: ключ записи (идентификатор).

        Исключения:
            Строки, не соответствующие формату, пропускаются без ошибки.

        Использование:
            chunks = load_metadata_entries("/prompts/metadata_list.txt")
        """
        print("✅ Инициализация списка метаданных")
        chunks = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    key, rest = line.split(":", 1)
                    chunks.append(Document(
                        page_content=rest.strip(),
                        metadata={"system": "metadata_list", "ids": key}
                    ))
                except ValueError:
                    continue  # Пропустить строки, не соответствующие формату
        return chunks
