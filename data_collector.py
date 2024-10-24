import httpx
import os
import asyncio
from models import Company, Server, Workstation, SessionLocal
from data_validator import clearify_server_data, clearify_pos_data
import datetime
from log import setup_logger
import logging
from aiolimiter import AsyncLimiter
from tqdm.asyncio import tqdm_asyncio
# from dotenv import load_dotenv


# load_dotenv()
# Настройка логирования
setup_logger(console_logging=False)
logger = logging.getLogger("ServiceDeskLogger")

# Получение значений переменных окружения
BASE_API_URL = f"{os.getenv('BASE_URL')}/services/rest/"
ACCESS_KEY = os.getenv("SDKEY")

limiter = AsyncLimiter(15, 1)

# Асинхронная функция для заполнения базы данных из ServiceDesk
async def initialize_database():
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        with SessionLocal() as session:
            logger.info("Инициализация базы данных начата")
            # Пример POST-запроса к ServiceDesk для получения списка компаний
            url = f"{BASE_API_URL}find/ou$company"
            payload = {
                "accessKey": ACCESS_KEY,
                "attrs": "adress,UUID,title,lastModifiedDate,KEsInUse,additionalName,parent,recipientAgreements"
            }
            try:
                async with limiter:
                    response = await client.post(url, params=payload)
            except httpx.TimeoutException as e:
                logger.error(f"Таймаут при получении списка компаний: {e}")
                return
            except Exception as e:
                logger.error(f"Произошла ошибка при получении списка компаний: {e}")
                return

            if response.status_code == 200:
                companies_data = response.json()
                tasks = []
                for company_data in tqdm_asyncio(companies_data, desc="Обработка компаний", unit="компания"):
                    logger.debug(f"Обработка компании UUID: {company_data['UUID']}")

                    # Проверка активности контракта
                    active_contract = False
                    for agreement_data in company_data.get('recipientAgreements', []):
                        if agreement_data['metaClass'] == 'agreement$agreement':
                            is_active = await process_agreement(client, agreement_data)
                            if is_active:
                                active_contract = True
                                break

                    # Создание компании в базе данных
                    company = Company(
                        uuid=company_data['UUID'],
                        title=company_data['title'],
                        address=company_data.get('adress', None),
                        last_modified_date=datetime.datetime.strptime(company_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S"),
                        additional_name=company_data.get('additionalName', None),
                        parent_uuid=company_data['parent']['UUID'] if company_data.get('parent') else None,
                        active_contract=active_contract
                    )
                    session.add(company)
                    logger.debug(f"Компания добавлена в сессию UUID: {company_data['UUID']}")

                    # Добавление оборудования компании
                    for equipment_data in company_data.get('KEsInUse', []):
                        if equipment_data['metaClass'] in ['objectBase$Server', 'objectBase$Workstation', 'objectBase$FR']:
                            tasks.append(process_equipment(client, equipment_data, company, session))

                semaphore = asyncio.Semaphore(20)
                async def semaphore_wrapper(task):
                    async with semaphore:
                        return await task
                tasks = [semaphore_wrapper(task) for task in tasks]

                for f in tqdm_asyncio.as_completed(tasks, desc="Обработка оборудования", unit="ед."):
                    await f
                # Асинхронное выполнение всех задач
                # await asyncio.gather(*tasks)
                session.commit()
                logger.info("База данных успешно инициализирована")

# Асинхронная функция для обработки контрактов
async def process_agreement(client, agreement_data):
    agreement_url = f"{BASE_API_URL}get/{agreement_data['UUID']}"
    agreement_params = {
        "accessKey": ACCESS_KEY,
        "attrs": "state,UUID"
    }
    try:
        async with limiter:
            response = await client.get(agreement_url, params=agreement_params)
    except httpx.TimeoutException as e:
        logger.error(f"Таймаут при проверке статуса контракта: {agreement_data['UUID']}: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при получении контракта {agreement_data['UUID']}: {e}")
        return False
    if response.status_code == 200:
        logger.debug(f"Проверка статуса контракта: {agreement_data['UUID']}")
        agreement_info = response.json()
        logger.debug(f"Статус контракта: {agreement_info['state']}")
        return agreement_info['state'] == 'active'
    return False

# Асинхронная функция для обработки оборудования
async def process_equipment(client, equipment_data, company, session):
    equipment_url = f"{BASE_API_URL}get/{equipment_data['UUID']}"
    if equipment_data['metaClass'] == 'objectBase$Server':
        equipment_params = {
            "accessKey": ACCESS_KEY,
            "attrs": "UniqueID,Teamviewer,RDP,AnyDesk,UUID,IP,CabinetLink,DeviceName,lastModifiedDate,iikoVersion,description,nameforclient"
        }
    elif equipment_data['metaClass'] == 'objectBase$Workstation':
        equipment_params = {
            "accessKey": ACCESS_KEY,
            "attrs": "Commentariy,Teamviewer,AnyDesk,DeviceName,lastModifiedDate,UUID"
        }
    else:
        return
    try:
        async with limiter:
            response = await client.get(equipment_url, params=equipment_params)
    except httpx.TimeoutException as e:
        logger.error(f"Таймаут при получении оборудования: {equipment_data['UUID']}: {e}")
        return
    except Exception as e:
        logger.error(f"Произошла ошибка при получении оборудования: {equipment_data['UUID']}: {e}")
        return
    if response.status_code == 200:
        equipment_info = response.json()

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
                iiko_version=equipment_info.get('iikoVersion', None),
                last_modified_date=datetime.datetime.strptime(equipment_info['lastModifiedDate'], "%Y.%m.%d %H:%M:%S"),
                description='{} {}'.format(
                    equipment_info.get('nameforclient', None),
                    equipment_info.get('RDP', None),
                    equipment_info.get('description', None)
                ),
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

async def validate_servers():
    logger.info("Начинается процесс валидации серверов")
    with SessionLocal() as session:
        servers = session.query(Server).all()
        tasks = []
        semaphore = asyncio.Semaphore(20)
        async def semaphore_wrapper(coro):
            async with semaphore:
                return await coro

        for server in tqdm_asyncio(servers, desc="Обработка серверов", unit="сервер"):
            logger.debug(f"Запуск валидации сервера UUID: {server.uuid}")
            tasks.append(semaphore_wrapper(validate_server_data(server, session)))
        
        await asyncio.gather(*tasks)
        session.commit()
    logger.info("Процесс валидации серверов завершен")

async def validate_workstations():
    logger.info("Начинается процесс валидации рабочих станций")
    with SessionLocal() as session:
        workstations = session.query(Workstation).all()
        tasks = []
        semaphore = asyncio.Semaphore(20)
        async def semaphore_wrapper(coro):
            async with semaphore:
                return await coro

        for workstation in tqdm_asyncio(workstations, desc="Обработка рабочих станций", unit="pos"):
            logger.debug(f"Запуск валидации рабочей станции UUID: {workstation.uuid}")
            tasks.append(semaphore_wrapper(validate_workstation_data(workstation, session)))

        await asyncio.gather(*tasks)
        session.commit()
    logger.info("Процесс валидации рабочих станций завершен")

async def validate_server_data(server, session):
    try:
        data = {
            'UniqueID': server.unique_id,
            'Teamviewer': server.teamviewer,
            'UUID': server.uuid,
            'RDP': server.rdp,
            'AnyDesk': server.anydesk,
            'IP': server.ip,
            'CabinetLink': server.cabinet_link,
            'litemanager_raw': server.description,
            'litemanager': server.litemanager,
        }

        logger.debug(f"Валидация сервера UUID: {server.uuid}, данные до валидации: {data}")

        # Вызов clearify_server_data
        updated_data = await clearify_server_data(data)

        logger.debug(f"Сервер UUID: {server.uuid}, данные после валидации: {updated_data}")

        # Обновление объекта сервера с валидированными данными
        server.unique_id = updated_data.get('UniqueID', server.unique_id)
        server.cabinet_link = updated_data.get('CabinetLink', server.cabinet_link)
        server.teamviewer = updated_data.get('Teamviewer', server.teamviewer)
        server.rdp = updated_data.get('RDP', server.rdp)
        server.anydesk = updated_data.get('AnyDesk', server.anydesk)
        server.litemanager = updated_data.get('litemanager', server.litemanager)

        if updated_data.get('IP') != server.ip:
            logger.debug(f"Обновление IP для сервера UUID {server.uuid}: {server.ip} -> {updated_data['IP']}")
            server.ip = updated_data['IP']

        session.add(server)

    except Exception as e:
        logger.error(f"Валидация сервера UUID: {server.uuid} завершилась с ошибкой: {e}")

async def validate_workstation_data(workstation, session):
    try:
        data = {
            'Teamviewer': workstation.teamviewer,
            'UUID': workstation.uuid,
            'AnyDesk': workstation.anydesk,
            'litemanager_raw': workstation.commentary,
            'litemanager': workstation.litemanager,
            'UUID': workstation.uuid,
        }

        logger.debug(f"Валидация рабочей станции UUID: {workstation.uuid}, данные до валидации: {data}")

        # Вызов clearify_workstation_data
        updated_data = await clearify_pos_data(data)

        logger.debug(f"Рабочая станция UUID: {workstation.uuid}, данные после валидации: {updated_data}")

        # Обновление объекта рабочей станции с валидированными данными
        workstation.teamviewer = updated_data.get('Teamviewer', workstation.teamviewer)
        workstation.anydesk = updated_data.get('AnyDesk', workstation.anydesk)
        workstation.litemanager = updated_data.get('litemanager', workstation.litemanager)

        session.add(workstation)

    except Exception as e:
        logger.error(f"Валидация рабочей станции UUID: {workstation.uuid} завершена с ошибкой: {e}")

def main():
    asyncio.run(run_all())

async def run_all():
    await initialize_database()
    await validate_servers()
    await validate_workstations()

if __name__ == "__main__":
    main()
