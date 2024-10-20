import re
import logging

# Настройка логирования
logger = logging.getLogger("ServiceDeskLogger")

# Определение паттернов для поиска серверов
IIKO_IT_PATTERN = r'^(https?://)?([a-zA-Z0-9-]+\.)?([a-zA-Z0-9-]+\.iiko\.it)'
SYRVE_ONLINE_PATTERN = r'^(https?://)?([a-zA-Z0-9-]+\.)?([a-zA-Z0-9-]+\.syrve\.online)'
CABINET_LINK_PATTERN = r'https://partners\.iiko\.ru/(ru|en)/cabinet/clients\.html\?mode=showOne&id='
REMOTE_ACCESS_ID_PATTERN = r'(\d\s*){9,10}'

# Функция для подготовки ссылки на партнерский кабинет
def validate_cabinet_link(cabinet_link: str) -> str:
    if isinstance(cabinet_link, str) and re.match(CABINET_LINK_PATTERN, cabinet_link):
        updated_link = re.sub(
            CABINET_LINK_PATTERN, 
            'https://partners.iiko.ru/v2/ru/cabinet/client-area/index.html?clientId=',
            cabinet_link
        )
        logger.info(f"Ссылка на кабинет обновлена: {updated_link}")
        return updated_link
    return cabinet_link

# Функция для проверки и валидации UniqueID
def validate_unique_id(unique_id: str) -> str:
    if unique_id is None or not isinstance(unique_id, str) or not re.match(r'^\d{3}-\d{3}-\d{3}$', unique_id):
        logger.warning(f"UID не задан или имеет неверный формат: {unique_id}")
        return 'NotSet'
    logger.info(f"UID корректен: {unique_id}")
    return unique_id

# Функция для очистки удаленных доступов (Teamviewer, AnyDesk)
def validate_remote_access_id(access_id_raw: str) -> str:
    match_id = None
    if access_id_raw:
        match_id = re.search(REMOTE_ACCESS_ID_PATTERN, access_id_raw)
    if match_id:
        access_id = match_id.group(0)
        return access_id
    else:
        logging.error(f"Invalid remote ID: {access_id_raw}")
        access_id = None
    return access_id


def validate_ip_address(ip_address: str) -> str:
    if ip_address and ('.iiko.it' in ip_address or '.syrve.online' in ip_address):
        # Обработка облачных серверов
        if '.iiko.it' in ip_address:
            match_ip = re.search(IIKO_IT_PATTERN, ip_address)
        elif '.syrve.online' in ip_address:
            match_ip = re.search(SYRVE_ONLINE_PATTERN, ip_address)
        else:
            match_ip = None
        if match_ip:
            domain = match_ip.group(3)
            updated_ip = f"{domain}:443"
            logger.info(f"Облачный IP преобразован: {updated_ip}")
            return updated_ip
    else:
                # Обработка локальных серверов и доменов первого-второго уровня
        match = re.search(r'^(https?://)?([a-zA-Z0-9.-]+)(:(\d+))?(\/.*)?$', ip_address)
        if match:
            domain = match.group(2)
            if 'iikoweb' in domain:
                return f'{domain}'
            port = match.group(4) if match.group(4) else '8080'  # По умолчанию используем порт 8080
            updated_ip = f"{domain}:{port}"
            logger.info(f"Локальный IP или домен преобразован: {updated_ip}")
            return updated_ip
        # Обработка локальных серверов
        else:
            match_ip = re.search(r'(\d+\.\d+\.\d+\.\d+)(:(\d+))?', ip_address) if ip_address else None
            if match_ip:
                ip = match_ip.group(1)
                port = match_ip.group(3) if match_ip.group(3) else '8080'
                updated_ip = f"{ip}:{port}"
                logger.info(f"Локальный IP преобразован: {updated_ip}")
                return updated_ip
            else:
                logger.warning(f"Не удалось распознать формат IP адреса: {ip_address}")
    return ip_address


# Основная функция для валидации данных
async def clearify_server_data(server_data: dict) -> dict:
    logger.info(f"Начало валидации данных сервера UUID: {server_data.get('UUID')}")

    # Подготовка ссылки на партнерский кабинет
    server_data['CabinetLink'] = validate_cabinet_link(server_data.get('CabinetLink', ''))

    # Проверка UID
    server_data['UniqueID'] = validate_unique_id(server_data.get('UniqueID', ''))

    # Проверка IP
    server_data['IP'] = validate_ip_address(server_data.get('IP', ''))

    # Очистка удаленных доступов (Teamviewer, AnyDesk, RDP)
    remote_access_fields = ['Teamviewer', 'AnyDesk', 'RDP']
    for field in remote_access_fields:
        if server_data.get(field):
            server_data[field] = validate_remote_access_id(server_data[field])

    # Извлечение LiteManager ID
    lm_match = re.search(r'MH_\d{5}', server_data.get('litemanager_raw', ''))
    server_data['litemanager'] = lm_match[0] if lm_match else ''

    logger.info(f"Валидация данных сервера UUID {server_data.get('UUID')} завершена")
    return server_data

async def clearify_pos_data(pos_data: dict) -> dict:
    logger.info(f"Начало валидации данных POS UUID: {pos_data.get('UUID')}")

    remote_access_fields = ['Teamviewer', 'AnyDesk']
    for field in remote_access_fields:
        if pos_data.get(field):
            pos_data[field] = validate_remote_access_id(pos_data[field])
    
    lm_match = re.findall(r'MH_\d{5}', pos_data.get('litemanager_raw', ''))
    pos_data['litemanager'] = lm_match[0] if lm_match else ''

    logger.info(f"Валидация данных POS UUID {pos_data.get('UUID')} завершена")
    return pos_data