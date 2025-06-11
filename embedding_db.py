from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from typing import Dict, List, Optional


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
        self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=self.embedding_model)

    def add_text(self, text: List[str], metadatas: List[Dict[str, str]] = None) -> None:
        """
        Добавляет текст в базу данных эмбеддингов с метаданными.

        :param text: Текст для сохранения в базе данных.
        :param metadatas: Словарь метаданных (например, {"категория": "заметки", "дата": "04.06.2025"}).
        """
        metadatas = metadatas or []  # Если метаданные не переданы, создаем пустой список
        self.vector_store.add_texts(texts=text, metadatas=metadatas)  # Записываем с эмбеддингами
        print(f"✅ Заметки добавлены")

    def retrieve_relevant_texts(self, query: str, k: int = 3, filter_metadata: Optional[Dict[str, str]] = None) -> List[
        str]:
        """
        Извлекает релевантные записи из базы данных на основе запроса и фильтрации по метаданным.

        :param query: Запрос пользователя.
        :param k: Количество релевантных записей для извлечения.
        :param filter_metadata: Словарь метаданных для фильтрации (например, {"категория": "заметки"}).
        :return: Список релевантных текстов.
        """
        retriever = self.vector_store.as_retriever(search_kwargs={"k": k, "filter": filter_metadata or {}})
        relevant_chunks = retriever.invoke(query)
        return [chunk.page_content for chunk in relevant_chunks]

    from typing import Optional, Dict, List, Any

    def get_notes(self, query_text: Optional[str] = "", k: int = 10,
                  filter_metadata: Optional[Dict[str, str]] = None,
                  get_metadata: bool = False,
                  word_for_search: dict = None) -> List[Dict[str, dict]] or List[str]:
        """
        Извлекает заметки, фильтруя их по метаданным и/или находя похожие тексты по эмбеддингам.
        Возвращает список словарей с текстами заметок и их метаданными (если указаны).

        :param query_text: Текстовый запрос для поиска похожих записей (если передан).
        :param k: Количество результатов.
        :param filter_metadata: Словарь метаданных для фильтрацииФормат:
        {"ключ": {"$eq": значение}, "числовое_поле": {"$gte": число}}
        :param get_metadata: Флаг, указывающий, нужно ли вернуть метаданные.
        :param word_for_search: слово или фраза для поиска документов
        :return: Список [{text: "...", metadata: {...}}] или [str]
        """
        print("Сейчас в базе", self.vector_store._collection.get())  # Показывает всю базу

        # Формируем словарь параметров запроса
        if query_text:
            # Поиск похожих записей по эмбеддингам и возможно метаданным
            # results = self.vector_store.similarity_search(query=query_text, k=k, filter=filter_metadata)
            print("filter_metadata", filter_metadata)
            results = self.vector_store.similarity_search(query=query_text, k=k, filter=filter_metadata)
            print("results", results)
            if not results:
                return []
            if get_metadata:
                # Формируем список заметок в формате [{text: "...", metadata: {...}}]
                # С метаданными или без них
                return [{"text": doc.page_content, "metadata": doc.metadata} for doc in results]
            return [doc.page_content for doc in results]

        else:
            # Фильтрация по метаданным
            param = {"where": filter_metadata}
            if word_for_search:
                # Активация поиска документа по слову
                param["where_document"] = word_for_search
            print("filter_metadata", param)
            results = self.vector_store.get(**param)
            print("Результат сразу после запроса", results)
            # print(self.vector_store._collection.get(include=["embeddings", "documents", "metadatas"]))  # Показывает всю базу
            if not results["documents"]:
                return []
            if get_metadata:
                # Формируем список заметок в формате [{text: "...", metadata: {...}}]
                # С метаданными или без них
                return [{"text": doc, "metadata": meta} for doc, meta in
                        zip(results["documents"], results["metadatas"])]
            return [doc for doc in results["documents"]]



    # def get_notes(self, filter_metadata: Optional[Dict[str, str]] = None, get_metadata: bool = False) -> List[Dict[str, Any]]:
    #     """
    #     Извлекает заметки, фильтруя их по метаданным (если переданы).
    #     Возвращает список словарей с текстами заметок и их метаданными (если указаны).
    #
    #     :param filter_metadata: Словарь метаданных для фильтрации (например, {"категория": "проект"}).
    #     :param get_metadata: Флаг, указывающий, нужно ли получать метаданные.
    #     :return: Список [{text: "...", metadata: {...}}]
    #     """
    #
    #     if filter_metadata:
    #         results = self.vector_store.get(where=filter_metadata)  # Фильтрация по метаданным
    #     else:
    #         results = self.vector_store.get()  # Получение всех записей
    #
    #     documents = results["documents"]
    #     metadatas = results["metadatas"]
    #
    #     # Формируем список заметок
    #     if get_metadata:
    #         return [{"text": doc, "metadata": meta} for doc, meta in zip(documents, metadatas)]
    #     return [doc for doc in documents]


# Пример использования
if __name__ == "__main__":
    # Установка параметров
    PERSIST_DIRECTORY = "./chroma_db"
    MODEL_NAME = "ai-forever/ru-en-RoSBERTa"

    # Инициализация базы данных эмбеддингов
    embedding_db = EmbeddingDatabase(persist_directory=PERSIST_DIRECTORY, model_name=MODEL_NAME)

    # Добавление заметок с метаданными
    embedding_db.add_text("Пример заметки для тестирования.", {"категория": "заметки", "дата": "04.06.2025"})
    embedding_db.add_text("Важная информация о проекте.", {"категория": "проект", "дата": "03.06.2025"})

    # Запрос релевантных записей без фильтрации
    results = embedding_db.retrieve_relevant_texts("тестирование")
    print("\n🔍 Найденные заметки:")
    for res in results:
        print(f"- {res}")

    # Запрос релевантных записей с фильтрацией по категории
    filtered_results = embedding_db.retrieve_relevant_texts("информация", filter_metadata={"категория": "проект"})
    print("\n🔍 Найденные заметки (категория: проект):")
    for res in filtered_results:
        print(f"- {res}")
