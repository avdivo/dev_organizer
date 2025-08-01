from typing import Dict, List, Optional, Tuple

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document


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

        ids, documents = self.load_metadata_entries("prompts/metadata_list.txt")
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embedding_model,
            ids=ids,
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
        print(f"✅ Заметки добавлены")

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
        print("-" * 40)
        print(f"Семантический поиск:\n Строка для поиска: {query_text}\nФильры: {filter_metadata}\n")
        results = self.vector_store.similarity_search_with_score(query=query_text, filter=filter_metadata)

        out = [
            {"metadata": doc.metadata, "page_content": doc.page_content}
            for doc, distance in results if distance <= limit
        ]
        # print("Результат семантического поиска:\n", results)
        print("Результат семантического поиска:\n", out)
        print("-" * 40)

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
        print("-" * 40)
        print(f"Поиск по фильтрам:\n {param}\n")
        results = self.vector_store.get(**param)

        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        # zip-уем попарно, если кол-во элементов совпадает
        out = [
            {"metadata": meta, "page_content": text}
            for text, meta in zip(documents, metadatas)
        ]
        # print("Результат поиска по фильтрам:\n", results)
        print("Результат поиска по фильтрам:\n", out)
        print("-" * 40)
        return out

    # def get_notes(self, query_text: Optional[str] = "", k: int = 10,
    #               filter_metadata: Optional[Dict[str, str]] = None,
    #               get_metadata: bool = False) -> List[Dict[str, dict]] or List[str]:
    #     """
    #     Извлекает заметки, фильтруя их по метаданным и/или находя похожие тексты по эмбеддингам.
    #     Возвращает список словарей с текстами заметок и их метаданными (если указаны).
    #
    #     :param query_text: Текстовый запрос для поиска похожих записей (если передан).
    #     :param k: Количество результатов.
    #     :param filter_metadata: Словарь метаданных для фильтрацииФормат:
    #     {"ключ": {"$eq": значение}, "числовое_поле": {"$gte": число}}
    #     :param get_metadata: Флаг, указывающий, нужно ли вернуть метаданные.
    #     :param word_for_search: слово или фраза для поиска документов
    #     :return: Список [{text: "...", metadata: {...}}] или [str]
    #     """
    #
    #     # Выводит все записи из базы
    #     # results = self.vector_store._collection.get(where={"user": {"$eq": "1"}})
    #     # for i in range(len(results["ids"])):
    #     #     print(f"ID: {results['ids'][i]}")
    #     #     print(f"Metadata: {results['metadatas'][i]}")
    #     #     print(f"Document: {results['documents'][i]}")
    #     #     print("-" * 40)
    #
    #     # Формируем словарь параметров запроса
    #     if query_text:
    #         # Поиск похожих записей по эмбеддингам и возможно метаданным
    #         # results = self.vector_store.similarity_search(query=query_text, k=k, filter=filter_metadata)
    #         print("-" * 40)
    #         print(f"Запрос:\n Строка для поиска: {query_text} Фильры: filter_metadata\n")
    #         results = self.vector_store.similarity_search_with_score(query=query_text, k=k, filter=filter_metadata)
    #         print("Результат семантического запроса", results)
    #         print("-" * 40)
    #         if not results:
    #             return []
    #         if get_metadata:
    #             # Формируем список заметок в формате [{text: "...", metadata: {...}}]
    #             # С метаданными или без них
    #             return [{"text": doc.page_content, "metadata": doc.metadata} for doc in results]
    #         return [doc.page_content for doc in results]
    #
    #     else:
    #         # Фильтрация по метаданным
    #         param = {"where": filter_metadata}
    #         if word_for_search:
    #             # Активация поиска документа по слову
    #             param["where_document"] = word_for_search
    #         print("-" * 40)
    #         print(f"Запрос:\n {param}\n")
    #         results = self.vector_store.get(**param)
    #         print("Результат фильтра", results)
    #         print("-" * 40)
    #         if not results["documents"]:
    #             return []
    #         if get_metadata:
    #             # Формируем список заметок в формате [{text: "...", metadata: {...}}]
    #             # С метаданными или без них
    #             return [{"text": doc, "metadata": meta} for doc, meta in
    #                     zip(results["documents"], results["metadatas"])]
    #         return [doc for doc in results["documents"]]

    def load_metadata_entries(self, filepath: str) -> Tuple[list, List]:
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
        metadata_names = []
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
                    metadata_names.append(key)
                except ValueError:
                    continue  # Пропустить строки, не соответствующие формату
        return metadata_names, chunks
