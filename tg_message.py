import requests
import subprocess
from config import TG_TOKEN

chat_id = "249503190"

def send_message(message: str) -> None:
    """
    Отправляет сообщение в телеграм
    Системного уведомления Ubuntu

    :param message:
    :return:
    """
    subprocess.run(["notify-send", "Органайзер", message])

    requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", params={
        "chat_id": chat_id,
        "text": message
    })
