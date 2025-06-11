import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from sql_db import SQLiteClient
from openai_client import OpenAIClient
from embedding_db import EmbeddingDatabase
from create_tables import SQLiteTableCreator


# Загрузка переменных окружения
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
TG_TOKEN = os.getenv("TG_TOKEN")
PERSIST_DIRECTORY = "./chroma_db"
MODEL_NAME = "ai-forever/ru-en-RoSBERTa"
# MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_LIST = "заметка"  # Список который должен существовать при старте системы

# Инициализация модели эмбеддингов и подключение к базе данных
print("Инициализация БД и модели эмбеддингов")
embedding_db = EmbeddingDatabase(persist_directory=PERSIST_DIRECTORY, model_name=MODEL_NAME)

# Инициализация LLM
# llm = ChatOpenAI(model="gpt-3.5-turbo", api_key=API_KEY)
llm = ChatOpenAI(model="gpt-4.1-nano", api_key=OPENAI_API_KEY)

print("Инициализация клиента OpenAI")
openai_client = OpenAIClient(api_key=OPENAI_API_KEY)

# Путь к дополнительной базе данных SQLite
db_path = "database.sqlite"

# Сначала создаем таблицы (при запуске)
table_creator = SQLiteTableCreator(db_path)
table_creator.create_tables_sync()

sql_db = SQLiteClient(db_path)

print("Инициализация службы оповещений")
# Инициализация APScheduler
scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}
)
