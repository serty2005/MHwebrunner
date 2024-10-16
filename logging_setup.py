import logging
import os
from dotenv import load_dotenv
from logging import handlers

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение уровня логирования из переменных окружения
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "app.log")

# Создание директории для логов, если она не существует
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# Форматирование сообщений лога
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s.%(funcName)s - %(message)s', "%Y-%m-%d %H:%M:%S.%f")

# Обработчик для вывода логов в файл
file_handler = handlers.RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Обработчик для вывода логов в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Функция для получения логгера в других модулях
def get_logger(name: str):
    module_logger = logging.getLogger(name)
    module_logger.setLevel(LOG_LEVEL)
    return module_logger

# Пример использования
if __name__ == "__main__":
    logger.info("Логирование настроено успешно.")