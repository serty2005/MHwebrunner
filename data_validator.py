import re
import logging
import datetime
from typing import Optional, Dict, Any

# Получаем логгер, настроенный в другом месте (например, sync_runner.py или log.py)
logger = logging.getLogger("ServiceDeskLogger")

# Определение паттернов для поиска
IIKO_IT_PATTERN = r'^(https?://)?([a-zA-Z0-9-]+\.)?([a-zA-Z0-9-]+\.iiko\.it)'
SYRVE_ONLINE_PATTERN = r'^(https?://)?([a-zA-Z0-9-]+\.)?([a-zA-Z0-9-]+\.syrve\.online)'

# Паттерн для поиска ID удаленного доступа (9 или 10 цифр)
REMOTE_ACCESS_ID_PATTERN = r'(\d\s*){9,10}'
# Паттерн для поиска LiteManager ID (MH_XXXXX) в произвольном тексте
LITEMANAGER_RAW_PATTERN = r'MH_\d{5}'

# Функция для определения типа компании (iiko/Syrve) по адресу сервера
def determine_company_type_from_ip(ip_address: Optional[str]) -> str:
    """
    Определяет тип компании ('iiko' или 'syrve') на основе IP адреса/домена сервера.
    По умолчанию возвращает 'iiko'.
    """
    if ip_address and isinstance(ip_address, str):
        if 'syrve' in ip_address.lower():
            return 'syrve'
    return 'iiko' # По умолчанию считаем iiko, если syrve не найдено

# Функция для подготовки ссылки на партнерский кабинет
def validate_cabinet_link(cabinet_link_raw: Optional[str], company_type: str) -> str:
    """
    Извлекает ID клиента из строки ссылки на партнерский кабинет (цифры после последнего '=').
    Формирует новую ссылку в формате pp.iiko.ru или pp.syrve.com с извлеченным ID.
    Если ID не найден или исходная ссылка пустая/некорректная, использует "N/A" вместо ID.
    Всегда возвращает строку.
    """
    client_id = "N/A" # Значение по умолчанию, если ID не будет найдено

    if isinstance(cabinet_link_raw, str) and cabinet_link_raw.strip():
        # Исходная строка не пустая, пытаемся найти '='
        if '=' in cabinet_link_raw:
            # Разделяем строку по последнему '=' и берем часть после него
            potential_id_str = cabinet_link_raw.split('=')[-1].strip()
            # Проверяем, что полученная строка состоит только из цифр
            if potential_id_str.isdigit():
                client_id = potential_id_str
                logger.debug(f"Извлечен client ID '{client_id}' из ссылки: '{cabinet_link_raw}'")
            else:
                logger.warning(f"Найдено '=', но часть после него не является числом: '{potential_id_str}' из '{cabinet_link_raw}'. Использован 'N/A'.")
        else:
            logger.warning(f"В строке ссылки на кабинет отсутствует '=': '{cabinet_link_raw}'. Использован 'N/A'.")
    else:
        logger.debug(f"Исходная строка ссылки на кабинет пустая или некорректная: '{cabinet_link_raw}'. Использован 'N/A'.")


    # Формируем итоговую ссылку в зависимости от типа компании
    if company_type == 'syrve':
        final_link = f"https://pp.syrve.com/en/cabinet/client-area/index.html?clientId={client_id}"
    else: # company_type == 'iiko'
        final_link = f"https://pp.iiko.ru/ru/cabinet/client-area/index.html?clientId={client_id}"

    logger.debug(f"Сформирована итоговая ссылка на кабинет: '{final_link}'")
    return final_link


# Функция для проверки и валидации UniqueID
def validate_unique_id(unique_id: Optional[str]) -> Optional[str]:
    """
    Валидирует формат UniqueID (XXX-XXX-XXX).
    Возвращает UniqueID или None, если формат неверный или отсутствует.
    """
    if unique_id is None or not isinstance(unique_id, str) or not re.match(r'^\d{3}-\d{3}-\d{3}$', unique_id.strip()):
        if unique_id and isinstance(unique_id, str) and unique_id.strip():
             logger.warning(f"UniqueID имеет неверный формат: '{unique_id}'. Возвращено None.")
        return None
    logger.debug(f"UniqueID корректен: '{unique_id.strip()}'")
    return unique_id.strip()

# Функция для очистки удаленных доступов (Teamviewer, AnyDesk)
def validate_remote_access_id(access_id_raw: Optional[str]) -> Optional[str]:
    """
    Извлекает ID удаленного доступа (9 или 10 цифр) из строки.
    Возвращает очищенный ID или None, если не найдено.
    """
    if not isinstance(access_id_raw, str) or not access_id_raw.strip():
        return None

    match_id = re.search(REMOTE_ACCESS_ID_PATTERN, access_id_raw)
    if match_id:
        access_id = match_id.group(0)
        cleaned_id = access_id.replace(' ', '') # Удаляем пробелы
        logger.debug(f"Найден и очищен ID удаленного доступа: '{access_id_raw.strip()}' -> '{cleaned_id}'")
        return cleaned_id
    else:
        logger.debug(f"Не удалось найти ID удаленного доступа по паттерну: '{access_id_raw.strip()}'. Возвращено None.")
        return None

# Функция для валидации и преобразования IP адреса/домена
def validate_ip_address(ip_address_raw: Optional[str]) -> Optional[str]:
    """
    Валидирует и преобразует строку IP адреса или домена.
    Пытается привести к формату host:port.
    Возвращает преобразованную строку или None, если не удалось распознать.
    """
    if not isinstance(ip_address_raw, str) or not ip_address_raw.strip():
        return None

    ip_address = ip_address_raw.strip()

    # 1. Обработка облачных адресов (.iiko.it, .syrve.online)
    match_cloud_iiko = re.search(IIKO_IT_PATTERN, ip_address)
    if match_cloud_iiko:
        domain = match_cloud_iiko.group(3)
        updated_ip = f"{domain}:443"
        logger.debug(f"Облачный IP (.iiko.it) преобразован: '{ip_address_raw}' -> '{updated_ip}'")
        return updated_ip

    match_cloud_syrve = re.search(SYRVE_ONLINE_PATTERN, ip_address)
    if match_cloud_syrve:
        domain = match_cloud_syrve.group(3)
        updated_ip = f"{domain}:443"
        logger.debug(f"Облачный IP (.syrve.online) преобразован: '{ip_address_raw}' -> '{updated_ip}'")
        return updated_ip

    # 2. Обработка локальных IP адресов (x.x.x.x) с опциональным портом
    match_ip_port = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?', ip_address)
    if match_ip_port:
        ip = match_ip_port.group(1)
        port = match_ip_port.group(2)
        # Простая проверка на валидность IP сегментов (0-255)
        try:
            if all(0 <= int(seg) <= 255 for seg in ip.split('.')):
                 updated_ip = f"{ip}:{port if port else '8080'}"
                 logger.debug(f"Локальный IP преобразован: '{ip_address_raw}' -> '{updated_ip}'")
                 return updated_ip
            else:
                 logger.warning(f"Невалидный формат сегментов IP адреса: '{ip_address_raw}'. Возвращено None.")
                 return None
        except ValueError:
             logger.warning(f"Ошибка при парсинге сегментов IP адреса: '{ip_address_raw}'. Возвращено None.")
             return None


    # 3. Обработка локальных доменов (без http/https, с/без порта)
    match_domain_port = re.search(r'^([a-zA-Z0-9.-]+)(?::(\d+))?$', ip_address)
    if match_domain_port:
        domain = match_domain_port.group(1)
        port = match_domain_port.group(2)
        # Можно добавить более строгую проверку домена, но пока оставим простую
        updated_ip = f"{domain}:{port if port else '8080'}"
        logger.debug(f"Локальный домен преобразован: '{ip_address_raw}' -> '{updated_ip}'")
        return updated_ip

    # Если ни один паттерн не совпал
    logger.warning(f"Не удалось распознать формат IP адреса или домена: '{ip_address_raw}'. Возвращено None.")
    return None

# Функция для извлечения LiteManager ID
def extract_litemanager_id(data: Dict[str, Any], fallback_text: Optional[str] = None) -> Optional[str]:
    """
    Извлекает LiteManager ID. Сначала проверяет прямое поле 'litemanagerID',
    затем пытается найти по паттерну в fallback_text.
    """
    # 1. Проверяем прямое поле 'litemanagerID' из данных ServiceDesk
    litemanager_id_direct = data.get('litemanagerID')
    if litemanager_id_direct and isinstance(litemanager_id_direct, str):
        # Можно добавить простую валидацию формата MH_\d{5} для прямого поля
        if re.match(LITEMANAGER_RAW_PATTERN, litemanager_id_direct.strip()):
             logger.debug(f"Найден LiteManager ID в прямом поле: '{litemanager_id_direct.strip()}'")
             return litemanager_id_direct.strip()
        else:
             logger.warning(f"Прямое поле litemanagerID имеет неверный формат: '{litemanager_id_direct.strip()}'. Игнорируем прямое поле.")


    # 2. Если прямого поля нет или оно невалидно, пытаемся найти по паттерну в fallback_text
    if fallback_text and isinstance(fallback_text, str):
        lm_match = re.search(LITEMANAGER_RAW_PATTERN, fallback_text)
        if lm_match:
            logger.debug(f"Найден LiteManager ID в тексте: '{lm_match[0]}'")
            return lm_match[0]

    # Если нигде не найдено
    logger.debug("LiteManager ID не найден ни в прямом поле, ни в тексте.")
    return None


# Функция для валидации и очистки данных сервера (синхронная)
def clearify_server_data(server_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Очищает и валидирует данные сервера, полученные из ServiceDesk API.
    Возвращает словарь с данными, готовыми для сохранения в БД (snake_case ключи).
    """
    logger.debug(f"Начало валидации данных сервера UUID: {server_data.get('UUID')}")

    cleaned_data = {}

    # Обязательное поле UUID
    cleaned_data['uuid'] = server_data.get('UUID')

    # Валидация и преобразование полей
    cleaned_data['unique_id'] = validate_unique_id(server_data.get('UniqueID'))
    cleaned_data['ip'] = validate_ip_address(server_data.get('IP'))

    # Определяем тип компании для формирования ссылки на кабинет
    company_type = determine_company_type_from_ip(cleaned_data['ip'])
    cleaned_data['cabinet_link'] = validate_cabinet_link(server_data.get('CabinetLink'), company_type)

    # Очистка удаленных доступов (Teamviewer, AnyDesk, RDP)
    cleaned_data['teamviewer'] = validate_remote_access_id(server_data.get('Teamviewer'))
    cleaned_data['rdp'] = validate_remote_access_id(server_data.get('RDP'))
    cleaned_data['anydesk'] = validate_remote_access_id(server_data.get('AnyDesk'))

    # Извлечение LiteManager ID
    # Для сервера пытаемся найти в прямом поле (если добавлено в attrs_map) или в описании/nameforclient
    raw_text_for_lm = f"{server_data.get('description', '')} {server_data.get('nameforclient', '')}"
    cleaned_data['litemanager'] = extract_litemanager_id(server_data, raw_text_for_lm)


    # Прямое копирование других полей, если они есть и нужны
    cleaned_data['device_name'] = server_data.get('DeviceName')
    cleaned_data['iiko_version'] = server_data.get('iikoVersion')
    # Объединяем nameforclient и description из SD в одно поле description в БД
    cleaned_data['description'] = '{} {}'.format(server_data.get('nameforclient', ''), server_data.get('description', '')).strip()

    cleaned_data['last_modified_date'] = datetime.datetime.strptime(server_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S") if server_data.get('lastModifiedDate') else None
    cleaned_data['owner_id'] = server_data.get('owner', {}).get('UUID') if server_data.get('owner') else None

    logger.debug(f"Валидация данных сервера UUID {cleaned_data.get('uuid')} завершена.")
    return cleaned_data

# Функция для валидации и очистки данных рабочей станции (POS) (синхронная)
def clearify_pos_data(pos_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Очищает и валидирует данные рабочей станции (POS), полученные из ServiceDesk API.
    Возвращает словарь с данными, готовыми для сохранения в БД (snake_case ключи).
    """
    logger.debug(f"Начало валидации данных POS UUID: {pos_data.get('UUID')}")

    cleaned_data = {}

    # Обязательное поле UUID
    cleaned_data['uuid'] = pos_data.get('UUID')

    # Очистка удаленных доступов (Teamviewer, AnyDesk)
    cleaned_data['teamviewer'] = validate_remote_access_id(pos_data.get('Teamviewer'))
    cleaned_data['anydesk'] = validate_remote_access_id(pos_data.get('AnyDesk'))

    # Извлечение LiteManager ID
    # Для рабочей станции пытаемся найти в прямом поле 'litemanagerID' или в Commentariy
    cleaned_data['litemanager'] = extract_litemanager_id(pos_data, pos_data.get('Commentariy'))

    # Прямое копирование других полей
    cleaned_data['device_name'] = pos_data.get('DeviceName')
    # Commentary из SD соответствует полю description в нашей модели Workstation
    cleaned_data['description'] = pos_data.get('Commentariy', '')

    cleaned_data['last_modified_date'] = datetime.datetime.strptime(pos_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S") if pos_data.get('lastModifiedDate') else None
    cleaned_data['owner_id'] = pos_data.get('owner', {}).get('UUID') if pos_data.get('owner') else None

    logger.debug(f"Валидация данных POS UUID {cleaned_data.get('uuid')} завершена.")
    return cleaned_data

# Функция для валидации и очистки данных фискального регистратора (ФР) (синхронная)
def clearify_fr_data(fr_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Очищает и валидирует данные фискального регистратора (ФР), полученные из ServiceDesk API.
    Возвращает словарь с данными, готовыми для сохранения в БД (snake_case ключи).
    """
    logger.debug(f"Начало валидации данных ФР UUID: {fr_data.get('UUID')}")

    cleaned_data = {}

    # Обязательное поле UUID
    cleaned_data['uuid'] = fr_data.get('UUID')

    # Прямое копирование и валидация полей
    # Убедимся, что ModelKKT и FFD являются словарями перед вызовом .get('title')
    model_kkt_data = fr_data.get('ModelKKT')
    cleaned_data['model_kkt'] = model_kkt_data.get('title') if isinstance(model_kkt_data, dict) else None

    ffd_data = fr_data.get('FFD')
    cleaned_data['ffd'] = ffd_data.get('title') if isinstance(ffd_data, dict) else None # Было code, изменил на title по attrs_map в services.py

    cleaned_data['fr_downloader'] = fr_data.get('FRDownloader')
    cleaned_data['rn_kkt'] = fr_data.get('RNKKT')
    cleaned_data['legal_name'] = fr_data.get('LegalName')
    cleaned_data['fr_serial_number'] = fr_data.get('FRSerialNumber')
    cleaned_data['fn_number'] = fr_data.get('FNNumber')

    # Валидация и преобразование дат
    # KKTRegDate и FNExpireDate приходят в формате "YYYY.MM.DD HH:MM:SS"
    cleaned_data['kkt_reg_date'] = None
    kkt_reg_date_str = fr_data.get('KKTRegDate')
    if kkt_reg_date_str:
        try:
            cleaned_data['kkt_reg_date'] = datetime.datetime.strptime(kkt_reg_date_str, "%Y.%m.%d %H:%M:%S")
        except ValueError:
            logger.warning(f"Неверный формат KKTRegDate для ФР {cleaned_data.get('uuid')}: '{kkt_reg_date_str}'.")

    cleaned_data['fn_expire_date'] = None
    fn_expire_date_str = fr_data.get('FNExpireDate')
    if fn_expire_date_str:
         try:
            cleaned_data['fn_expire_date'] = datetime.datetime.strptime(fn_expire_date_str, "%Y.%m.%d %H:%M:%S")
         except ValueError:
            logger.warning(f"Неверный формат FNExpireDate для ФР {cleaned_data.get('uuid')}: '{fn_expire_date_str}'.")

    cleaned_data['last_modified_date'] = datetime.datetime.strptime(fr_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S") if fr_data.get('lastModifiedDate') else None
    cleaned_data['owner_id'] = fr_data.get('owner', {}).get('UUID') if fr_data.get('owner') else None

    logger.debug(f"Валидация данных ФР UUID {cleaned_data.get('uuid')} завершена.")
    return cleaned_data
