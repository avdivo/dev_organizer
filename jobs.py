from datetime import datetime
from tg_message import send_message

def reminder_job(job_id=None, message=None):
    print(f"[{datetime.now()}] Задание с ID: {job_id}\n{message}")
    send_message(message)  # Выводим сообщение
