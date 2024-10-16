from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Company, Server, Workstation, SessionLocal
from starlette.responses import HTMLResponse
import os

# Инициализация FastAPI приложения
app = FastAPI()

# Инициализация шаблонизатора Jinja2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

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
    companies = db.query(Company).all()
    return templates.TemplateResponse("index.html", {"request": request, "companies": companies})
