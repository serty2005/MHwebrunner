# --- START OF FILE schemas.py ---

from pydantic import BaseModel
from typing import List, Optional
import datetime

# Модель для результата поиска компании
class CompanySearchResult(BaseModel):
    uuid: str
    title: Optional[str] = None
    address: Optional[str] = None
    additional_name: Optional[str] = None
    active_contract: Optional[bool] = None
    # Добавляем другие поля, если они нужны для отображения в результатах поиска
    # Например, parent_uuid, но в результатах поиска он, вероятно, не нужен.

    class Config:
        from_attributes = True # Pydantic v2+
        # orm_mode = True # Pydantic v1 (если используете старую версию)

# Модель для результата поиска сервера
class ServerSearchResult(BaseModel):
    uuid: str
    device_name: Optional[str] = None
    ip: Optional[str] = None
    unique_id: Optional[str] = None
    teamviewer: Optional[str] = None
    rdp: Optional[str] = None
    anydesk: Optional[str] = None
    litemanager: Optional[str] = None
    # owner_id: Optional[str] = None # Не обязательно включать owner_id в результат поиска

    class Config:
        from_attributes = True

# Модель для результата поиска рабочей станции
class WorkstationSearchResult(BaseModel):
    uuid: str
    device_name: Optional[str] = None
    teamviewer: Optional[str] = None
    anydesk: Optional[str] = None
    litemanager: Optional[str] = None
    description: Optional[str] = None
    # owner_id: Optional[str] = None

    class Config:
        from_attributes = True

# Модель для результата поиска фискального регистратора
class FiscalRegisterSearchResult(BaseModel):
    uuid: str
    rn_kkt: Optional[str] = None
    model_kkt: Optional[str] = None
    fn_expire_date: Optional[datetime.datetime] = None
    fr_serial_number: Optional[str] = None
    fn_number: Optional[str] = None
    legal_name: Optional[str] = None
    # owner_id: Optional[str] = None

    # Конфигурация модели Pydantic для отключения предупреждения о "model_"
    model_config = {
        'from_attributes': True, # Для работы с SQLAlchemy ORM объектами
        'protected_namespaces': () # Отключаем проверку защищенных пространств имен
    }


# Модель общего ответа на поисковый запрос
class SearchResultResponse(BaseModel):
    companies: List[CompanySearchResult]
    servers: List[ServerSearchResult]
    workstations: List[WorkstationSearchResult]
    fiscal_registers: List[FiscalRegisterSearchResult]

# --- END OF FILE schemas.py ---