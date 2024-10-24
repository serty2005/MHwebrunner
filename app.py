from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Company, SessionLocal
from starlette.responses import HTMLResponse
import os
import threading
import asyncio

# Инициализация FastAPI приложения
app = FastAPI()

# Инициализация шаблонизатора Jinja2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

def generate_servicedesk_link(uuid: str) -> str:
    base_url = os.getenv("BASE_URL")
    if base_url:
        servicedesk_link = f"{base_url}/operator/#uuid:{uuid}"
        return servicedesk_link
    return "#"

templates.env.globals['generate_servicedesk_link'] = generate_servicedesk_link

# Получение базы данных
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = None
    try:
        request.state.db = SessionLocal()
        response = await call_next(request)
    finally:
        request.state.db.close()
    return response

# Функция для получения сессии базы данных
def get_db(request: Request):
    return request.state.db

# Главная страница с блоками компаний
@app.get("/", response_class=HTMLResponse)
async def read_companies(request: Request):
    db: Session = get_db(request)
    top_level_companies = db.query(Company).filter(Company.parent_uuid == None).all()
    return templates.TemplateResponse("index.html", {"request": request, "top_level_companies": top_level_companies})

# Страница инициализации
@app.get("/init", response_class=HTMLResponse)
async def init_page(request: Request):
    return templates.TemplateResponse("init.html", {"request": request})

# Менеджер для хранения активных WebSocket-подключений
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Обработчик WebSocket-соединения
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Ожидаем сообщения от клиента (если нужно)
            data = await websocket.receive_text()
            if data == "start_init":
                # Запускаем инициализацию в отдельном потоке
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, run_initialization, manager)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def run_initialization(manager: ConnectionManager):
    import sys
    import data_collector

    # Перенаправляем stdout
    original_stdout = sys.stdout
    sys.stdout = ProgressIO(manager)

    try:
        data_collector.main()
    except Exception as e:
        # Отправляем сообщение об ошибке
        asyncio.run(manager.send_message(f"Ошибка: {str(e)}"))
    finally:
        # Восстанавливаем stdout
        sys.stdout = original_stdout
        # Уведомляем клиента об окончании
        asyncio.run(manager.send_message("Инициализация завершена."))

class ProgressIO:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    def write(self, message):
        # Отправляем каждую строку на клиентскую сторону
        asyncio.run(self.manager.send_message(message))

    def flush(self):
        pass  # Не требуется в данном случае