import httpx
import os
import asyncio
from models import Company, Equipment, Server, Workstation, SessionLocal
from data_validator import clearify_server_data
import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение значений переменных окружения
BASE_API_URL = "https://myhoreca.itsm365.com/sd/services/rest/"
ACCESS_KEY = os.getenv("SDKEY")


# Асинхронная функция для заполнения базы данных из ServiceDesk
async def initialize_database():
    async with httpx.AsyncClient() as client:
        with SessionLocal() as session:
            print("Инициализация базы данных начата")
            # Пример POST-запроса к ServiceDesk для получения списка компаний
            url = f"{BASE_API_URL}find/ou$company"
            payload = {
                "accessKey": ACCESS_KEY,
                "attrs": "adress,UUID,title,lastModifiedDate,KEsInUse,additionalName,parent,recipientAgreements"
            }
            response = await client.post(url, params=payload)
            if response.status_code == 200:
                companies_data = response.json()
                tasks = []
                for company_data in companies_data:
                    print(f"Обработка компании UUID: {company_data['UUID']}")

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
                    print(f"Компания добавлена в сессию UUID: {company_data['UUID']}")

                    # Добавление оборудования компании
                    for equipment_data in company_data.get('KEsInUse', []):
                        if equipment_data['metaClass'] in ['objectBase$Server', 'objectBase$Workstation', 'objectBase$FR']:
                            tasks.append(process_equipment(client, equipment_data, company, session))

                # Асинхронное выполнение всех задач
                await asyncio.gather(*tasks)
                session.commit()
                print("База данных успешно инициализирована")

# Асинхронная функция для обработки контрактов
async def process_agreement(client, agreement_data):
    agreement_url = f"{BASE_API_URL}get/{agreement_data['UUID']}"
    agreement_params = {
        "accessKey": ACCESS_KEY,
        "attrs": "state,UUID"
    }
    response = await client.get(agreement_url, params=agreement_params)
    if response.status_code == 200:
        agreement_info = response.json()
        return agreement_info['state'] == 'active'
    return False

# Асинхронная функция для обработки оборудования
async def process_equipment(client, equipment_data, company, session):
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
        return

    response = await client.get(equipment_url, params=equipment_params)
    if response.status_code == 200:
        equipment_info = response.json()
        last_modified_date = datetime.datetime.strptime(equipment_info['lastModifiedDate'], "%Y.%m.%d %H:%M:%S")

        if equipment_data['metaClass'] == 'objectBase$Server':
            # server_data = await clearify_server_data(equipment_info)
            server = Server(
                uuid=equipment_info['UUID'],
                device_name=equipment_info['DeviceName'],
                unique_id=equipment_info.get('UniqueID', None),
                teamviewer=equipment_info.get('Teamviewer', None),
                rdp=equipment_info.get('RDP', None),
                anydesk=equipment_info.get('AnyDesk', None),
                ip=equipment_info.get('IP', None),
                cabinet_link=equipment_info.get('CabinetLink', None),
                cloud=equipment_info.get('Cloud', False) == True,
                iiko_version=equipment_info.get('iikoVersion', None),
                last_modified_date=last_modified_date,
                owner=company
            )
            session.add(server)
            print(f"Сервер добавлен в сессию UUID: {equipment_info['UUID']}")
        elif equipment_data['metaClass'] == 'objectBase$Workstation':
            workstation = Workstation(
                uuid=equipment_info['UUID'],
                device_name=equipment_info['DeviceName'],
                teamviewer=equipment_info.get('Teamviewer', None),
                anydesk=equipment_info.get('AnyDesk', None),
                commentary=equipment_info.get('Commentariy', None),
                last_modified_date=last_modified_date,
                owner=company
            )
            session.add(workstation)
            print(f"Рабочая станция добавлена в сессию UUID: {equipment_info['UUID']}")

async def validate_servers():
    print("Начинается процесс валидации серверов")
    async with httpx.AsyncClient() as client:
        with SessionLocal() as session:
            servers = session.query(Server).all()
            tasks = []
            for server in servers:
                print(f"Запуск валидации сервера UUID: {server.uuid}")
                tasks.append(validate_server_data(client, server, session))
            await asyncio.gather(*tasks)
            session.commit()
    print("Процесс валидации серверов завершен")

async def validate_server_data(client, server, session):
    # Подготовка данных из объекта сервера
    try:
        data = {
            'UUID': server.uuid,
            'DeviceName': server.device_name,
            'UniqueID': server.unique_id,
            'Teamviewer': server.teamviewer,
            'RDP': server.rdp,
            'AnyDesk': server.anydesk,
            'IP': server.ip,
            'CabinetLink': server.cabinet_link,
            'Cloud': server.cloud,
            'iikoVersion': server.iiko_version,
            'lastModifiedDate': server.last_modified_date.strftime("%Y.%m.%d %H:%M:%S"),
        }

        print(f"Валидация сервера UUID: {server.uuid}, данные до валидации: {data}")

        # Вызов clearify_server_data
        updated_data = await clearify_server_data(data)

        print(f"Сервер UUID: {server.uuid}, данные после валидации: {updated_data}")

        # Обновление объекта сервера с валидированными данными
        server.unique_id = updated_data.get('UniqueID', server.unique_id)
        server.server_type = updated_data.get('server_type', server.server_type)
        server.cabinet_link = updated_data.get('cabinet_link', server.cabinet_link)

        # Обновляем IP только если он изменился (т.е. сервер ответил)
        if updated_data.get('IP') != server.ip:
            print(f"Обновление IP для сервера UUID {server.uuid}: {server.ip} -> {updated_data['IP']}")
            server.ip = updated_data['IP']

        session.add(server)

    except Exception as e:
        print(f"Валидация сервера UUID: {server.uuid} завершилась с ошибкой: {e}")

# Основной код, который можно запустить для инициализации
def main():
    asyncio.run(run_all())

async def run_all():
    # await initialize_database()
    await validate_servers()

if __name__ == "__main__":
    main()