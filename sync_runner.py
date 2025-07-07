import asyncio
import logging
import datetime
import sys # Импортируем sys для os.exit
# Импортируем AsyncSessionLocal, Base, engine, check_db_connection
from models import AsyncSessionLocal, Base, engine, check_db_connection
# Импортируем ServiceDeskService
from services import ServiceDeskService
import os
from dotenv import load_dotenv
# import random # Больше не используется в текущей тестовой логике
# import httpx # Больше не используется в текущей тестовой логике
# Импортируем функцию настройки логгирования
from log import setup_logger

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логгирования должна быть вызвана первой
# Уровень INFO будет выводиться в консоль, DEBUG+ в файл
setup_logger(console_logging=True)

# Получаем логгер после настройки
logger = logging.getLogger("SyncRunner")

# Асинхронная функция для создания таблиц БД, если они не существуют
async def init_db():
    """Проверяет наличие таблиц в БД и создает их, если необходимо."""
    logger.info("Проверка и создание таблиц БД начаты.")
    try:
        async with engine.begin() as conn:
            # run_sync позволяет выполнять синхронные операции с асинхронным движком
            # Это безопасно для DDL операций (CREATE TABLE)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Проверка и создание таблиц БД завершены.")
    except Exception as e:
        logger.error(f"Ошибка при проверке/создании таблиц БД: {e}", exc_info=True)
        # Генерируем исключение, чтобы вызывающий код мог его обработать (например, sys.exit)
        raise

# Асинхронная функция для запуска полной синхронизации
async def run_sync():
    """Запуск полной инкрементальной синхронизации данных из ServiceDesk."""
    try:
        # Создаем экземпляр ServiceDeskService без аргументов
        service = ServiceDeskService()

        # Начало синхронизации
        start_time = datetime.datetime.now()
        logger.info("Начало полной синхронизации данных.")

        # Запуск синхронизации через сервис. Передаем фабрику сессий.
        await service.sync_all_data(AsyncSessionLocal)

        # Завершение синхронизации.
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logger.info(f"Полная синхронизация завершена. Длительность: {duration}")

    except Exception as e:
        # Логгируем ошибку и генерируем исключение для main
        logger.error(f"Ошибка при выполнении полной синхронизации: {e}", exc_info=True)
        raise # Пробрасываем исключение

# Асинхронная функция для запуска тестовой синхронизации
async def test_sync():
    """
    Запуск тестовой синхронизации.
    В текущей инкрементальной логике, тестовая синхронизация
    запускает полный проход.
    """
    logger.info("Запуск тестовой синхронизации (полный инкрементальный проход).")

    # Для тестовой синхронизации можно временно установить более детальный уровень логгирования
    service_logger = logging.getLogger("ServiceDeskLogger")
    original_level = service_logger.level
    # Проверяем, что текущий уровень не ниже DEBUG, чтобы не понизить его случайно
    if original_level > logging.DEBUG:
         service_logger.setLevel(logging.DEBUG)
         logger.info("Уровень логгирования ServiceDeskLogger временно установлен в DEBUG для теста.")
    else:
         logger.info("Уровень логгирования ServiceDeskLogger уже DEBUG или ниже. Изменение не требуется.")


    try:
        # Тестовый запуск просто вызывает полную синхронизацию
        await run_sync()
    finally:
        # Возвращаем уровень логгирования, если меняли
        if 'original_level' in locals() and service_logger.level != original_level:
            service_logger.setLevel(original_level)
            logger.info("Уровень логгирования ServiceDeskLogger восстановлен.")

    logger.info("Тестовая синхронизация завершена.")


if __name__ == "__main__":
    # Основной блок выполнения скрипта

    async def main():
        # Шаг 1: Проверяем подключение к БД с повторными попытками
        # Если подключение не удастся, check_db_connection сгенерирует исключение,
        # и выполнение main() прервется.
        try:
            # Увеличил количество попыток и задержку для надежности
            await check_db_connection(retries=20, delay=5)
        except ConnectionError as e:
             logger.critical(f"Не удалось установить соединение с базой данных: {e}", exc_info=True)
             sys.exit(1) # Завершаем скрипт с кодом ошибки
        except Exception as e:
             logger.critical(f"Неожиданная ошибка при проверке подключения к БД: {e}", exc_info=True)
             sys.exit(1)

        # Шаг 2: Проверяем и создаем таблицы БД (если подключение успешно)
        try:
            await init_db()
        except Exception as e:
            logger.critical(f"Критическая ошибка при инициализации или создании таблиц БД: {e}", exc_info=True)
            sys.exit(1) # Завершаем скрипт с кодом ошибки

        # Шаг 3: Запускаем синхронизацию (полную или тестовую)
        try:
            if len(sys.argv) > 1 and sys.argv[1] == "--test":
                await test_sync()
            else:
                await run_sync()
        except Exception as e:
             logger.critical(f"Критическая ошибка при выполнении синхронизации: {e}", exc_info=True)
             sys.exit(1) # Завершаем скрипт с кодом ошибки

        logger.info("Выполнение скрипта завершено успешно.")
        sys.exit(0) # Завершаем скрипт с кодом успеха

    # Запускаем основной асинхронный блок
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Выполнение скрипта прервано пользователем.")
        sys.exit(130) # Код завершения для Ctrl+C
    except Exception as e:
        # Этот except перехватит любые исключения, которые не были обработаны внутри main
        # Но основные критические ошибки уже завершают процесс через sys.exit
        logger.critical(f"Непредвиденная ошибка при запуске asyncio.run(main()): {e}", exc_info=True)
        sys.exit(1)