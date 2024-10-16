# Установка необходимых библиотек:
# pip install httpx python-dotenv

import httpx
import os
import time
from sqlalchemy.orm import Session
from logging_setup import get_logger
from models import Company, Agreement, Equipment, Server, Workstation, SessionLocal
import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение значений переменных окружения
BASE_API_URL = "https://myhoreca.itsm365.com/sd/services/rest/"
ACCESS_KEY = os.getenv("SDKEY")
# HEADERS = {"Content-Type": "application/json"}

if not os.path.exists('logs'):
    os.makedirs('logs')

# Настройка логгера
log_filename = f"logs/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logger = get_logger(__name__)

# Функция для заполнения базы данных из ServiceDesk
def initialize_database():
    with SessionLocal() as session:
        logger.info("Инициализация базы данных начата")
        # Пример POST-запроса к ServiceDesk для получения списка компаний
        url = f"{BASE_API_URL}find/ou$company"
        payload = {
            "accessKey": ACCESS_KEY,
            "attrs": "adress,UUID,title,lastModifiedDate,KEsInUse,additionalName,parent,recipientAgreements"
        }
        response = httpx.post(url, params=payload)
        if response.status_code == 200:
            companies_data = response.json()
            for company_data in companies_data:
                logger.info(f"Обработка компании UUID: {company_data['UUID']}")
                # Создание компании в базе данных
                company = Company(
                    uuid=company_data['UUID'],
                    title=company_data['title'],
                    address=company_data.get('adress', None),
                    last_modified_date=datetime.datetime.strptime(company_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S"),
                    additional_name=company_data.get('additionalName', None),
                    parent_uuid=company_data['parent']['UUID'] if company_data.get('parent') else None
                )
                session.add(company)
                logger.info(f"Компания добавлена в сессию UUID: {company_data['UUID']}")
                
                # Добавление контрактов компании
                for agreement_data in company_data.get('recipientAgreements', []):
                    if agreement_data['metaClass'] == 'agreement$agreement':
                        agreement_url = f"{BASE_API_URL}get/{agreement_data['UUID']}"
                        agreement_params = {
                            "accessKey": ACCESS_KEY,
                            "attrs": "state,UUID"
                        }
                        agreement_response = httpx.get(agreement_url, params=agreement_params)
                        if agreement_response.status_code == 200:
                            agreement_info = agreement_response.json()
                            agreement = Agreement(
                                uuid=agreement_info['UUID'],
                                title=agreement_data['title'],
                                meta_class=agreement_data['metaClass'],
                                company=company
                            )
                            # Добавление статуса контракта
                            agreement.state = agreement_info.get('state')
                            session.add(agreement)
                            logger.info(f"Контракт добавлен в сессию UUID: {agreement_info['UUID']}")
                        # time.sleep(0.5)  # Минимальная задержка между запросами
                
                # Добавление оборудования компании
                for equipment_data in company_data.get('KEsInUse', []):
                    if equipment_data['metaClass'] in ['objectBase$Server', 'objectBase$Workstation', 'objectBase$FR']:
                        equipment_url = f"{BASE_API_URL}get/{equipment_data['UUID']}"
                        if equipment_data['metaClass'] == 'objectBase$Server':
                            equipment_params = {
                                "accessKey": ACCESS_KEY,
                                "attrs": "UniqueID,Teamviewer,RDP,AnyDesk,UUID,IP,CabinetLink,DeviceName,lastModifiedDate,Cloud,iikoVersion"
                            }
                        elif equipment_data['metaClass'] == 'objectBase$Workstation':
                            equipment_params = {
                                "accessKey": ACCESS_KEY,
                                "attrs": "Commentariy,Teamviewer,AnyDesk,DeviceName,lastModifiedDate,UUID"
                            }
                        else:
                            continue

                        equipment_response = httpx.get(equipment_url, params=equipment_params)
                        if equipment_response.status_code == 200:
                            equipment_info = equipment_response.json()
                            if equipment_data['metaClass'] == 'objectBase$Server':
                                server = Server(
                                    uuid=equipment_info['UUID'],
                                    device_name=equipment_info['DeviceName'],
                                    unique_id=equipment_info.get('UniqueID', None),
                                    teamviewer=equipment_info.get('Teamviewer', None),
                                    rdp=equipment_info.get('RDP', None),
                                    anydesk=equipment_info.get('AnyDesk', None),
                                    ip=equipment_info.get('IP', None),
                                    cabinet_link=equipment_info.get('CabinetLink', None),
                                    cloud=equipment_info.get('Cloud', 'false') == 'true',
                                    iiko_version=equipment_info.get('iikoVersion', None),
                                    last_modified_date=datetime.datetime.strptime(equipment_info['lastModifiedDate'], "%Y.%m.%d %H:%M:%S"),
                                    owner=company
                                )
                                session.add(server)
                                logger.info(f"Сервер добавлен в сессию UUID: {equipment_info['UUID']}")
                            elif equipment_data['metaClass'] == 'objectBase$Workstation':
                                workstation = Workstation(
                                    uuid=equipment_info['UUID'],
                                    device_name=equipment_info['DeviceName'],
                                    teamviewer=equipment_info.get('Teamviewer', None),
                                    anydesk=equipment_info.get('AnyDesk', None),
                                    commentary=equipment_info.get('Commentariy', None),
                                    last_modified_date=datetime.datetime.strptime(equipment_info['lastModifiedDate'], "%Y.%m.%d %H:%M:%S"),
                                    owner=company
                                )
                                session.add(workstation)
                                logger.info(f"Рабочая станция добавлена в сессию UUID: {equipment_info['UUID']}")
                        # time.sleep(0.5)  # Минимальная задержка между запросами
            
            session.commit()
            logger.info("База данных успешно инициализирована")

# Основной код, который можно запустить для инициализации
def main():
    initialize_database()
    
if __name__ == "__main__":
    main()