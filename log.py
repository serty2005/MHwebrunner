import logging
import os
from datetime import datetime

def setup_logger(console_logging=True):
    if len(logging.getLogger().handlers) > 0:
        # Логгер уже настроен, выходим
        return

    # Проверка на переменную окружения для отключения логов в файл
    if os.getenv("DISABLE_FILE_LOGGING") == "1":
        # Полное отключение логирования
        logging.disable(logging.CRITICAL)
    else:
        # Получаем текущее время для имени файла лога
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log")

        # Создаем директорию для логов, если ее еще нет
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_filepath = os.path.join(log_dir, log_filename)

        # Настраиваем логгер
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Создаем форматтер
        formatter = logging.Formatter('%(asctime)s.%(msecs)04d - %(levelname)s - %(module)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # Создаем обработчик для записи лога в файл
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Создаем обработчик для вывода лога в консоль
        if console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

# Пример использования логгера
if __name__ == "__main__":
    setup_logger(console_logging=False)
    logger = logging.getLogger("ServiceDeskLogger")
    logger.info("Логгер успешно инициализирован.")
    logger.debug("Это сообщение для отладки.")
    logger.warning("Это предупреждающее сообщение.")
    logger.error("Это сообщение об ошибке.")
    logger.critical("Это критическое сообщение.")