import os
from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from logger import Logger
from sql_db import SQLiteClient
from provider_client import AIClient
from embedding_db import EmbeddingDatabase
from create_tables import SQLiteTableCreator

# Загрузка переменных окружения
load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
TG_TOKEN = os.getenv("TG_TOKEN")
PERSIST_DIRECTORY = "./chroma_db"
MODEL_NAME = "ai-forever/ru-en-RoSBERTa"
# MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_LIST = "заметка"  # Список который должен существовать при старте системы

# Инициализация модели эмбеддингов и подключение к базе данных
print("✅ Инициализация БД и модели эмбеддингов")
embedding_db = EmbeddingDatabase(persist_directory=PERSIST_DIRECTORY, model_name=MODEL_NAME)

# Инициализация LLM
# llm = ChatOpenAI(model="gpt-4.1-nano", api_key=COMETAPI_KEY)

print("✅ Инициализация клиента модели")
provider_client = AIClient()

# Путь к дополнительной базе данных SQLite
db_path = "database.sqlite"

# Сначала создаем таблицы (при запуске)
table_creator = SQLiteTableCreator(db_path)
table_creator.create_tables_sync()

sql_db = SQLiteClient(db_path)

print("✅ Инициализация службы оповещений")
# Инициализация APScheduler
scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}
)
