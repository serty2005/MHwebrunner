from fastapi import FastAPI, Request, BackgroundTasks, HTTPException # Импортируем HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
# Импортируем AsyncSession для тайп-хинтинга в middleware и эндпоинтах
from sqlalchemy.ext.asyncio import AsyncSession
# Импортируем все модели и фабрику асинхронных сессий
from models import Company, Server, Workstation, FiscalRegister, AsyncSessionLocal, check_db_connection
from starlette.responses import HTMLResponse
import os
from services import ServiceDeskService
import logging
# Импортируем SQLAlchemyError для обработки ошибок
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
# Импортируем функцию настройки логгирования
from log import setup_logger

# Импортируем Pydantic модели для ответов API
from typing import List, Optional
import datetime

from schemas import (
    CompanySearchResult,
    ServerSearchResult,
    WorkstationSearchResult,
    FiscalRegisterSearchResult,
    SearchResultResponse
)

setup_logger(console_logging=True)
# Получаем логгер, настроенный в другом месте
logger = logging.getLogger("ServiceDeskLogger")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Обработчик событий жизненного цикла FastAPI приложения.
    Выполняется при старте приложения (код до yield)
    и при остановке приложения (код после yield).
    """
    logger.info("Запуск FastAPI приложения. Выполнение lifespan startup.")
    # --- Код, выполняемый при старте приложения ---
    # Проверяем подключение к базе данных с повторными попытками
    try:
        # Увеличил количество попыток и задержку для надежности
        await check_db_connection(retries=20, delay=5)
        logger.info("Lifespan startup завершен. База данных доступна.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при подключении к БД во время startup: {e}", exc_info=True)
        raise # Пробрасываем исключение, чтобы Uvicorn его увидел

    # TODO: Здесь можно добавить инициализацию таблиц, если они еще не созданы sync_runner'ом
    # from models import Base, engine
    # async with engine.begin() as conn:
    #      await conn.run_sync(Base.metadata.create_all)
    # logger.info("Проверка и создание таблиц БД завершены в lifespan.")


    # --- После yield приложение начинает принимать запросы ---
    yield

    # --- Код, выполняемый при остановке приложения ---
    logger.info("Остановка FastAPI приложения. Выполнение lifespan shutdown.")
    logger.info("Lifespan shutdown завершен.")


# Инициализация FastAPI приложения с указанием обработчика lifespan
app = FastAPI(lifespan=lifespan) # Передаем обработчик lifespan при создании приложения

# Инициализация шаблонизатора Jinja2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Монтирование статических файлов (CSS, JS, favicon и т.д.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Функция-хелпер для генерации ссылки на объект в ServiceDesk
def generate_servicedesk_link(uuid: str) -> str:
    """Генерирует ссылку для открытия объекта по UUID в интерфейсе оператора ServiceDesk."""
    base_url = os.getenv("BASE_URL")
    if base_url:
        clean_base_url = base_url.rstrip('/')
        servicedesk_link = f"{clean_base_url}/operator/#uuid:{uuid}"
        logger.debug(f"Сгенегирована ссылка SD для UUID {uuid}: {servicedesk_link}")
        return servicedesk_link
    logger.warning(f"Переменная окружения BASE_URL не установлена. Не удалось сгенерировать ссылку SD для UUID {uuid}.")
    return "#"

# Добавляем функцию generate_servicedesk_link в глобальные переменные шаблонизатора,
# чтобы ее можно было вызывать напрямую из HTML-шаблона (если еще используется старый рендеринг)
# Для нового рендеринга через JS, передадим BASE_URL в контекст шаблона.
templates.env.globals['generate_servicedesk_link'] = generate_servicedesk_link

# Middleware для управления жизненным циклом асинхронной сессии базы данных
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    """
    Создает новую асинхронную сессию БД для каждого HTTP-запроса,
    прикрепляет ее к request.state и закрывает после завершения запроса.
    """
    async_session = AsyncSessionLocal()
    try:
        # Прикрепляем сессию к состоянию запроса
        request.state.db = async_session
        logger.debug("Асинхронная сессия БД создана для запроса.")
        # Передаем запрос следующему middleware или обработчику эндпоинта
        response = await call_next(request)
    except Exception as e:
        # Логгируем ошибку, если что-то пошло не так в процессе обработки запроса
        logger.error(f"Ошибка при обработке запроса в middleware сессии БД: {e}", exc_info=True)
        # Важно откатить сессию при ошибке, если она была создана и активна
        # Проверяем с помощью hasattr и is_active
        if hasattr(request.state, 'db') and request.state.db.is_active:
             try:
                await async_session.rollback()
                logger.debug("Асинхронная сессия БД откатана из-за ошибки в запросе.")
             except Exception as rollback_e:
                 logger.error(f"Ошибка при откате сессии БД в middleware: {rollback_e}", exc_info=True)
        # Пробрасываем исключение дальше
        raise # Пробрасываем исключение, чтобы FastAPI/Uvicorn его обработали (например, вернули 500)
    finally:
        # Гарантированно закрываем сессию после завершения запроса
        # Проверяем, что сессия была создана и не закрыта ранее
        if hasattr(request.state, 'db') and request.state.db.is_active:
             try:
                await request.state.db.close()
                logger.debug("Асинхронная сессия БД закрыта после запроса.")
             except Exception as close_e:
                 logger.error(f"Ошибка при закрытии сессии БД в middleware: {close_e}", exc_info=True)

    return response
# Функция для получения асинхронной сессии базы данных из состояния запроса
def get_db(request: Request) -> AsyncSession:
    """
    Возвращает асинхронную сессию БД, прикрепленную middleware к состоянию запроса.
    """
    return request.state.db


# Главная страница - теперь только поисковый интерфейс
@app.get("/", response_class=HTMLResponse)
async def search_page(request: Request):
    """
    Обрабатывает запрос на главную страницу.
    Рендерит шаблон index.html, который содержит только поисковую форму
    и контейнеры для результатов.
    """
    # Передаем BASE_URL в шаблон для формирования ссылок на SD в JS
    base_sd_url = os.getenv("BASE_URL", "").rstrip('/')
    return templates.TemplateResponse("index.html", {"request": request, "base_sd_url": base_sd_url})


# Новый эндпоинт для серверного поиска
@app.get("/api/search", response_model=SearchResultResponse)
async def search_entities(
    request: Request,
    term: Optional[str] = None, # Параметр поискового запроса
    show_inactive: bool = True # Параметр для фильтрации неактивных компаний
):
    """
    Принимает поисковый запрос и возвращает результаты из БД.
    """
    db: AsyncSession = get_db(request)
    service = ServiceDeskService()

    # Проверяем, что поисковый запрос не пустой или не состоит только из пробелов
    if not term or not term.strip():
        # Можно вернуть пустые результаты или результаты по умолчанию (например, верхние компании)
        # Пока вернем пустые результаты, если запрос пустой
        logger.info("Получен пустой или некорректный поисковый запрос.")
        return SearchResultResponse(companies=[], servers=[], workstations=[], fiscal_registers=[])

    search_term = term.strip()
    logger.info(f"Получен поисковый запрос: '{search_term}', Показывать неактивные: {show_inactive}")

    try:
        # Вызываем метод поиска из сервиса
        results = await service.search_entities(db, search_term, show_inactive)
        logger.info(f"Поиск завершен. Найдено: Компаний={len(results.companies)}, Серверов={len(results.servers)}, Рабочих станций={len(results.workstations)}, ФР={len(results.fiscal_registers)}")
        return results
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при выполнении поискового запроса '{search_term}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка при выполнении поиска в базе данных")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при выполнении поискового запроса '{search_term}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Произошла ошибка при поиске")


# Эндпоинт для запуска синхронизации данных из SD в фоновом режиме
@app.post("/sync/servicedesk")
async def sync_servicedesk_data(request: Request, background_tasks: BackgroundTasks):
    """
    Запускает полную инкрементальную синхронизацию данных из ServiceDesk
    в фоновой задаче.
    """
    service = ServiceDeskService()
    background_tasks.add_task(service.sync_all_data, AsyncSessionLocal)
    logger.info("Запрос на синхронизацию данных из ServiceDesk получен. Фоновая задача запущена.")
    return {"message": "Синхронизация данных из ServiceDesk запущена в фоновом режиме"}

# Эндпоинт для запуска синхронизации данных с FTP в фоновом режиме (заглушка)
@app.post("/sync/ftp")
async def sync_ftp_data(request: Request, background_tasks: BackgroundTasks):
    """
    Заглушка: Запускает синхронизацию данных с FTP в фоновой задаче.
    """
    service = ServiceDeskService()
    background_tasks.add_task(service.sync_ftp_data, AsyncSessionLocal)
    logger.info("Запрос на синхронизацию данных с FTP получен. Фоновая задача запущена (заглушка).")
    return {"message": "Синхронизация данных с FTP запущена в фоновом режиме (заглушка)"}
