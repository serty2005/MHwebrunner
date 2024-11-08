import httpx
from sqlalchemy.orm import Session
from models import Company, Agreement, Server, Workstation
import datetime

setup_logger(console_logging=False)
logger = logging.getLogger("ServiceDeskLogger")

# Получение значений переменных окружения
BASE_API_URL = f"{os.getenv('BASE_URL')}/services/rest/"
ACCESS_KEY = os.getenv("SDKEY")

limiter = AsyncLimiter(45, 1)


# Асинхронная функция для получения объекта из ServiceDesk по UUID и обновления данных в базе
async def get_by_uuid(client: httpx.AsyncClient, uuid: str, db_session: Session, base_api_url: str, access_key: str) -> None:
    url = f"{base_api_url}get/{uuid}"
    params = {
        "accessKey": access_key,
        "attrs": "*"  # Здесь можно указать конкретные атрибуты, если нужно оптимизировать запрос
    }
    response = await client.get(url, params=params)
    if response.status_code == 200:
        object_data = response.json()
        # Определяем, к какому классу принадлежит объект и обновляем его в базе
        if object_data.get('metaClass') == 'ou$company':
            await update_company(object_data, db_session)
        elif object_data.get('metaClass') == 'objectBase$Server':
            await update_server(object_data, db_session)
        elif object_data.get('metaClass') == 'objectBase$Workstation':
            await update_workstation(object_data, db_session)
        elif object_data.get('metaClass') == 'agreement$agreement':
            await update_agreement(object_data, db_session)
        db_session.commit()
    else:
        raise Exception(f"Не удалось получить данные по UUID {uuid}: {response.status_code}")
