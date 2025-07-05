from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from models import Company, Server, Workstation, SessionLocal
from starlette.responses import HTMLResponse
import os
from services import ServiceDeskService

# Инициализация FastAPI приложения
app = FastAPI()

# Инициализация шаблонизатора Jinja2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory="static"), name="static")

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

# Эндпоинт для синхронизации данных
@app.post("/sync")
async def sync_data(request: Request, background_tasks: BackgroundTasks):
    db: Session = get_db(request)
    service = ServiceDeskService(db)
    background_tasks.add_task(service.sync_all_data)
    return {"message": "Синхронизация данных запущена"}
