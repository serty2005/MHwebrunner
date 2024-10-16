import re
import httpx
import xml.etree.ElementTree as ET

# Определение паттернов для поиска серверов
IIKO_IT_PATTERN = r'^(https?://)?([a-zA-Z0-9-]+\.)?([a-zA-Z0-9-]+\.iiko\.it)'
SYRVE_ONLINE_PATTERN = r'^(https?://)?([a-zA-Z0-9-]+\.)?([a-zA-Z0-9-]+\.syrve\.online)'
CABINET_LINK_PATTERN = r'https://partners\.iiko\.ru/(ru|en)/cabinet/clients\.html\?mode=showOne&id='
REMOTE_ACCESS_ID_PATTERN = r'(\d\s*){9,10}'

# Асинхронная функция для получения информации о сервере
async def get_server_info(server_ip: str) -> str:
    url = f"{server_ip}/resto/get_server_info.jsp?encoding=UTF-8"
    print(f"Запрос информации о сервере по URL: {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=2)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            edition = root.find('edition').text
            if edition == 'default':
                print(f"Сервер {server_ip} определен как 'iikoOffice'")
                return 'iikoOffice'
            elif edition == 'chain':
                print(f"Сервер {server_ip} определен как 'iikoChain'")
                return 'iikoChain'
            else:
                return 'Unknown Edition'

    except httpx.TimeoutException:
        print(f"Превышено время ожидания запроса к серверу {server_ip}")
        return 'offline'
    except httpx.RequestError as e:
        print(f"Ошибка при выполнении запроса к серверу {server_ip}: {e}")
        return 'offline'
    except httpx.HTTPStatusError as e:
        print(f"HTTP ошибка при обращении к серверу {server_ip}: {e.response.status_code}")
        return 'offline'
    except ET.ParseError:
        print(f"Ошибка парсинга XML ответа от сервера {server_ip}")
        return 'offline'
    except Exception as e:
        print(f"Неизвестная ошибка при обращении к серверу {server_ip}: {e}")
        return 'offline'

async def clearify_server_data(data: dict) -> dict:
    print(f"Начало валидации данных сервера UUID: {data.get('UUID')}")
    # Подготовка ссылки на сервер (поле IP)
    server_link = data.get('IP', '')
    if server_link and ('.iiko.it' in server_link or '.syrve.online' in server_link):
        if '.iiko.it' in server_link:
            cloud_match = re.search(IIKO_IT_PATTERN, server_link)
        elif '.syrve.online' in server_link:
            cloud_match = re.search(SYRVE_ONLINE_PATTERN, server_link)
        else:
            cloud_match = None
        if cloud_match:
            server_link = cloud_match.group(3)
            server_type = await get_server_info(f"https://{server_link}")
            data['server_type'] = server_type
            if server_type != 'offline':
                data['IP'] = server_link
    else:
        lt_match = re.search(r'(\d+\.\d+\.\d+\.\d+)(:(\d+))?', server_link)
        if lt_match:
            lt_link = f'{lt_match.group(1)}:{lt_match.group(3)}'
            server_type = await get_server_info(lt_link)
            data['server_type'] = server_type
            if server_type != 'offline':
                data['IP'] = lt_link
        else:
            data['server_type'] = 'unknown'
            print(f"Не удалось распознать формат IP адреса сервера UUID {data.get('UUID')}")


    # Подготовка ссылки на кабинет
    cabinet_link = data.get('cabinet_link', '')
    if isinstance(cabinet_link, str) and re.match(CABINET_LINK_PATTERN, cabinet_link):
        cabinet_link = re.sub(
            CABINET_LINK_PATTERN, 
            'https://partners.iiko.ru/v2/ru/cabinet/client-area/index.html?clientId=', cabinet_link
        )
        print(f"Ссылка на кабинет обновлена для сервера UUID {data.get('UUID')}: {cabinet_link}")
 
    data['cabinet_link'] = cabinet_link

    # Подготовка UID
    unique_id = data.get('UniqueID', '')
    if unique_id is None or not isinstance(unique_id, str) or not re.match(r'^\d{3}-\d{3}-\d{3}$', unique_id):
        data['UniqueID'] = 'NotSet'   
        print(f"UID не задан или имеет неверный формат для сервера UUID {data.get('UUID')}")
    else:
        print(f"UID корректен для сервера UUID {data.get('UUID')}: {data['UniqueID']}")

    print(f"Валидация данных сервера UUID {data.get('UUID')} завершена")
    
    return data