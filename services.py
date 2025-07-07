import httpx
import asyncio
from typing import Optional, List, Dict, Any
import logging
from aiolimiter import AsyncLimiter
import os
import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

# Импортируем валидаторы, которые теперь возвращают snake_case ключи
from data_validator import clearify_server_data, clearify_pos_data, clearify_fr_data
from models import Company, Server, Workstation, FiscalRegister
# Импортируем репозитории
from repositories import CompanyRepository, ServerRepository, WorkstationRepository, FiscalRegisterRepository

logger = logging.getLogger("ServiceDeskLogger")
# Ограничитель запросов к API ServiceDesk
limiter = AsyncLimiter(45, 1) # 45 запросов в секунду

from schemas import SearchResultResponse, CompanySearchResult, ServerSearchResult, WorkstationSearchResult, FiscalRegisterSearchResult

class ServiceDeskService:
    # Удаляем session_factory из __init__
    def __init__(self):
        self.base_api_url = f"{os.getenv('BASE_URL')}/services/rest/"
        self.access_key = os.getenv("SDKEY")
        # Убедимся, что ключи доступа установлены
        if not self.base_api_url or not self.access_key:
             logger.critical("Переменные окружения BASE_URL или SDKEY не установлены. Работа с ServiceDesk API невозможна.")
             # Можно выбросить исключение или обрабатывать ошибки при каждом запросе.
             # Пока просто логгируем, ошибки будут возникать при попытке HTTP запросов.

    async def check_agreement_active(self, client: httpx.AsyncClient, agreement_data: dict) -> bool:
        """Проверка активности контракта по его UUID."""
        agreement_uuid = agreement_data.get('UUID')
        if not agreement_uuid:
            logger.warning("Передан объект контракта без UUID.")
            return False

        agreement_url = f"{self.base_api_url}get/{agreement_uuid}"
        agreement_params = {
            "accessKey": self.access_key,
            "attrs": "state,UUID"
        }
        try:
            # Проверяем, что ключи доступа доступны перед запросом
            if not self.access_key or not self.base_api_url:
                 logger.error("Отсутствуют ключи доступа к ServiceDesk API. Пропуск проверки контракта.")
                 return False

            async with limiter: # Применяем ограничение частоты запросов
                response = await client.get(agreement_url, params=agreement_params)
            response.raise_for_status() # Выбросит исключение для кодов 4xx/5xx
            agreement_info = response.json()
            logger.debug(f"Проверка статуса контракта: {agreement_uuid}, статус: {agreement_info.get('state')}")
            return agreement_info.get('state') == 'active'
        except httpx.TimeoutException as e:
            logger.error(f"Таймаут при проверке статуса контракта {agreement_uuid}: {e}")
            return False
        except httpx.HTTPStatusError as e:
             logger.error(f"Ошибка HTTP при проверке статуса контракта {agreement_uuid} (Статус: {e.response.status_code}): {e}")
             return False
        except Exception as e:
            logger.error(f"Ошибка при получении контракта {agreement_uuid}: {e}", exc_info=True)
            return False

    async def fetch_entity_list(self, client: httpx.AsyncClient, meta_class: str, attrs: str) -> List[Dict]:
        """
        Получение списка сущностей определенного метакласса из ServiceDesk
        с минимальными атрибутами (UUID, lastModifiedDate, owner/parent).
        """
        url = f"{self.base_api_url}find/{meta_class}"
        payload = {
            "accessKey": self.access_key,
            "attrs": attrs # Запрашиваем только необходимые атрибуты для инкрементальной проверки
        }
        try:
             # Проверяем, что ключи доступа доступны перед запросом
            if not self.access_key or not self.base_api_url:
                 logger.error("Отсутствуют ключи доступа к ServiceDesk API. Пропуск получения списка.")
                 return []

            async with limiter: # Применяем ограничение частоты запросов
                response = await client.post(url, params=payload)
            response.raise_for_status() # Выбросит исключение для кодов 4xx/5xx
            logger.info(f"Успешно получен список сущностей для метакласса: {meta_class}, количество: {len(response.json())}")
            return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Таймаут при получении списка {meta_class}: {e}")
            return []
        except httpx.HTTPStatusError as e:
             logger.error(f"Ошибка HTTP при получении списка {meta_class} (Статус: {e.response.status_code}): {e}")
             return []
        except Exception as e:
            logger.error(f"Произошла ошибка при получении списка {meta_class}: {e}", exc_info=True)
            return []

    async def fetch_entity_details(self, client: httpx.AsyncClient, uuid: str, meta_class: str) -> Optional[Dict]:
        """Получение полной информации о конкретной сущности по UUID."""
        url = f"{self.base_api_url}get/{uuid}"
        # Определяем, какие атрибуты нужны для каждого метакласса
        # Используем словарь аттрибутов
        attrs_map = {
            'ou$company': "adress,UUID,title,lastModifiedDate,additionalName,parent,recipientAgreements",
            'objectBase$Server': "UniqueID,Teamviewer,RDP,AnyDesk,UUID,IP,CabinetLink,DeviceName,lastModifiedDate,iikoVersion,description,nameforclient,owner,litemanagerID", # Добавил litemanagerID
            'objectBase$Workstation': "Commentariy,Teamviewer,AnyDesk,DeviceName,litemanagerID,lastModifiedDate,UUID,owner",
            'objectBase$FR': "UUID,ModelKKT,lastModifiedDate,owner,FFD,FRDownloader,RNKKT,KKTRegDate,FNExpireDate,LegalName,FRSerialNumber,FNNumber"
        }
        attrs = attrs_map.get(meta_class)
        if not attrs:
            logger.warning(f"Неизвестный метакласс для получения деталей: {meta_class}. UUID: {uuid}. Пропуск.")
            return None

        params = {
            "accessKey": self.access_key,
            "attrs": attrs
        }
        try:
             # Проверяем, что ключи доступа доступны перед запросом
            if not self.access_key or not self.base_api_url:
                 logger.error(f"Отсутствуют ключи доступа к ServiceDesk API. Пропуск получения деталей для {meta_class} {uuid}.")
                 return None

            async with limiter: # Применяем ограничение частоты запросов
                response = await client.get(url, params=params)
            response.raise_for_status() # Выбросит исключение для кодов 4xx/5xx
            logger.debug(f"Успешно получены детали для {meta_class} {uuid}")
            return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Таймаут при получении деталей {meta_class} {uuid}: {e}")
            return None
        except httpx.HTTPStatusError as e:
             logger.error(f"Ошибка HTTP при получении деталей {meta_class} {uuid} (Статус: {e.response.status_code}): {e}")
             return None
        except Exception as e:
            logger.error(f"Ошибка при получении деталей {meta_class} {uuid}: {e}", exc_info=True)
            return None

    async def process_company_data(self, client: httpx.AsyncClient, company_data: Dict) -> Optional[Dict]:
        """
        Обработка данных компании: проверка контракта, подготовка данных для репозитория.
        Требует httpx.AsyncClient для асинхронной проверки контрактов.
        """
        try:
            # Проверка активности контракта
            active_contract = False
            # recipientAgreements - это список объектов, нужно найти среди них agreement$agreement
            # Убедимся, что recipientAgreements существует и является списком
            agreements = company_data.get('recipientAgreements')
            if isinstance(agreements, list):
                for agreement_data in agreements:
                    # Убедимся, что agreement_data - это словарь и имеет metaClass
                    if isinstance(agreement_data, dict) and agreement_data.get('metaClass') == 'agreement$agreement':
                        is_active = await self.check_agreement_active(client, agreement_data)
                        if is_active:
                            active_contract = True
                            break # Найден активный контракт, дальше можно не искать
            elif agreements is not None:
                 logger.warning(f"Поле 'recipientAgreements' для компании {company_data.get('UUID')} не является списком: {type(agreements)}")


            # Подготовка данных компании для сохранения в БД (snake_case ключи)
            company_info = {
                'uuid': company_data.get('UUID'),
                'title': company_data.get('title'),
                'address': company_data.get('adress'),
                # lastModifiedDate парсится здесь
                'last_modified_date': datetime.datetime.strptime(company_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S") if company_data.get('lastModifiedDate') else None,
                'additional_name': company_data.get('additionalName'),
                # Исправление ошибки: проверяем, что parent не None перед вызовом .get('UUID')
                'parent_uuid': company_data.get('parent', None).get('UUID') if company_data.get('parent') else None,
                'active_contract': active_contract
            }
            # Логгируем обработанные данные
            logger.debug(f"Обработаны данные компании {company_info.get('uuid')}: parent_uuid={company_info.get('parent_uuid')}, active_contract={company_info.get('active_contract')}")
            return company_info
        except Exception as e:
            logger.error(f"Ошибка при обработке данных компании {company_data.get('UUID', 'N/A')}: {e}", exc_info=True)
            return None

    # process_server_data, process_workstation_data, process_fr_data теперь используют валидаторы,
    # которые сами добавляют last_modified_date и owner_id в snake_case формате.
    # Эти функции просто вызывают валидаторы.

    async def process_server_data(self, server_data: Dict) -> Optional[Dict]:
        """
        Обработка данных сервера: валидация, подготовка данных для репозитория.
        Вызывает clearify_server_data.
        """
        try:
            # clearify_server_data теперь возвращает словарь с snake_case ключами,
            # включая last_modified_date и owner_id
            cleaned_data = clearify_server_data(server_data)
            logger.debug(f"Обработаны данные сервера {cleaned_data.get('uuid')}: owner_id={cleaned_data.get('owner_id')}")
            return cleaned_data
        except Exception as e:
            logger.error(f"Ошибка при обработке данных сервера {server_data.get('UUID', 'N/A')}: {e}", exc_info=True)
            return None

    async def process_workstation_data(self, workstation_data: Dict) -> Optional[Dict]:
        """
        Обработка данных рабочей станции: валидация, подготовка данных для репозитория.
        Вызывает clearify_pos_data.
        """
        try:
            # clearify_pos_data теперь возвращает словарь с snake_case ключами,
            # включая last_modified_date и owner_id
            cleaned_data = clearify_pos_data(workstation_data)
            logger.debug(f"Обработаны данные рабочей станции {cleaned_data.get('uuid')}: owner_id={cleaned_data.get('owner_id')}")
            return cleaned_data
        except Exception as e:
            logger.error(f"Ошибка при обработке данных рабочей станции {workstation_data.get('UUID', 'N/A')}: {e}", exc_info=True)
            return None

    async def process_fr_data(self, fr_data: Dict) -> Optional[Dict]:
        """
        Обработка данных ФР: валидация, подготовка данных для репозитория.
        Вызывает clearify_fr_data.
        """
        try:
            # clearify_fr_data теперь возвращает словарь с snake_case ключами,
            # включая last_modified_date и owner_id
            cleaned_data = clearify_fr_data(fr_data)
            logger.debug(f"Обработаны данные ФР {cleaned_data.get('uuid')}: owner_id={cleaned_data.get('owner_id')}")
            return cleaned_data
        except Exception as e:
            logger.error(f"Ошибка при обработке данных ФР {fr_data.get('UUID', 'N/A')}: {e}", exc_info=True)
            return None


    # Принимаем session_factory в качестве аргумента
    async def sync_data_incrementally(self, session_factory: async_sessionmaker):
        """
        Инкрементальная синхронизация данных по этапам:
        1. Компании.
        2. Оборудование (Серверы, Рабочие станции, ФР).
        Это гарантирует наличие компаний-владельцев перед синхронизацией оборудования.
        Использует переданную фабрику сессий для создания сессий внутри.
        """

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client: # Увеличил таймаут
            logger.info("Начало инкрементальной синхронизации данных (поэтапно)")

            # Определяем, какие метаклассы мы синхронизируем, их атрибуты и функции обработки
            # Группируем по этапам
            sync_configs = {
                'companies': {
                    'meta_classes': ['ou$company'],
                    'configs': {
                        'ou$company': {
                            # Добавил parent в list_attrs для проверки иерархии на этапе списка
                            'list_attrs': "UUID,lastModifiedDate,title,parent",
                            'repo_class': CompanyRepository,
                            'process_func': self.process_company_data,
                            'db_model_class': Company
                        }
                    }
                },
                'equipment': {
                    'meta_classes': ['objectBase$Server', 'objectBase$Workstation', 'objectBase$FR'],
                    'configs': {
                        'objectBase$Server': {
                            'list_attrs': "UUID,lastModifiedDate,owner,DeviceName",
                            'repo_class': ServerRepository,
                            'process_func': self.process_server_data,
                            'db_model_class': Server
                        },
                        'objectBase$Workstation': {
                            'list_attrs': "UUID,lastModifiedDate,owner,DeviceName",
                            'repo_class': WorkstationRepository,
                            'process_func': self.process_workstation_data,
                            'db_model_class': Workstation
                        },
                        'objectBase$FR': {
                            'list_attrs': "UUID,lastModifiedDate,owner,RNKKT",
                            'repo_class': FiscalRegisterRepository,
                            'process_func': self.process_fr_data,
                            'db_model_class': FiscalRegister
                        }
                    }
                }
                # TODO: Добавить другие этапы, если появятся сущности с другими зависимостями
            }

            # Собираем UUID всех сущностей из БД перед синхронизацией
            # Это нужно для быстрой проверки даты изменения без получения полного объекта
            db_uuids_with_dates = {}
            db_all_uuids = {} # Дополнительно собираем все UUID из БД для проверки на удаление (хотя удаление пока отключено)
            logger.info("Сбор текущих UUID и дат изменения из локальной БД.")
            # Используем временную сессию из фабрики для этого чтения
            async with session_factory() as session:
                # Итерируем по всем метаклассам, которые мы собираемся синхронизировать
                all_meta_classes = [mc for stage in sync_configs.values() for mc in stage['meta_classes']]
                for meta_class in all_meta_classes:
                    # Находим конфигурацию для этого метакласса
                    config = None
                    for stage in sync_configs.values():
                        if meta_class in stage['meta_classes']:
                            config = stage['configs'].get(meta_class)
                            break

                    if config and config.get('db_model_class'):
                         try:
                             # Выполняем прямой select запрос к таблице модели для получения UUID и last_modified_date
                             result = await session.execute(
                                 select(config['db_model_class'].uuid, config['db_model_class'].last_modified_date)
                             )
                             # Сохраняем результаты в словаре {uuid: last_modified_date}
                             db_uuids_with_dates[meta_class] = {uuid: date for uuid, date in result.all()}
                             db_all_uuids[meta_class] = set(db_uuids_with_dates[meta_class].keys()) # Сохраняем набор UUID
                             logger.debug(f"Собрано {len(db_uuids_with_dates[meta_class])} UUID с датами для {meta_class} из БД.")
                         except Exception as e:
                              logger.error(f"Ошибка при сборе UUID и дат для {meta_class} из БД: {e}", exc_info=True)
                              db_uuids_with_dates[meta_class] = {} # В случае ошибки сохраняем пустой словарь
                              db_all_uuids[meta_class] = set()
                    else:
                         logger.warning(f"Для метакласса {meta_class} отсутствует полная конфигурация в sync_configs. Пропуск сбора UUID из БД.")
                         db_uuids_with_dates[meta_class] = {}
                         db_all_uuids[meta_class] = set()


            # Шаг 1: Получаем списки UUID и дат изменения из SD для всех метаклассов параллельно
            # Это делается один раз для всех метаклассов перед поэтапной обработкой
            sd_entity_lists_raw = {} # Словарь для хранения сырых списков {meta_class: [items]}
            list_fetch_tasks = []
            # Собираем все метаклассы для запроса списков
            all_meta_classes_for_fetch = [mc for stage in sync_configs.values() for mc in stage['meta_classes']]
            for meta_class in all_meta_classes_for_fetch:
                 # Находим конфигурацию для этого метакласса, чтобы получить list_attrs
                 config = None
                 for stage in sync_configs.values():
                     if meta_class in stage['meta_classes']:
                         config = stage['configs'].get(meta_class)
                         break
                 if config and config.get('list_attrs'):
                     list_fetch_tasks.append(self.fetch_entity_list(client, meta_class, config['list_attrs']))
                 else:
                     logger.warning(f"Для метакласса {meta_class} отсутствует list_attrs в sync_configs. Пропуск получения списка из SD.")

            # Выполняем все задачи получения списков параллельно
            results = await asyncio.gather(*list_fetch_tasks)

            # Сопоставляем результаты обратно с метаклассами, которые запрашивали списки
            fetched_meta_classes = [mc for stage in sync_configs.values() for mc in stage['meta_classes'] if stage['configs'].get(mc) and config['list_attrs']] # Исправлена логика сопоставления

            for i, meta_class in enumerate(fetched_meta_classes):
                 # Проверяем, что индекс i находится в пределах результатов results
                 if i < len(results):
                     sd_entity_lists_raw[meta_class] = results[i]
                     logger.debug(f"Получено {len(results[i])} сущностей для {meta_class} из SD.")
                 else:
                     logger.error(f"Несоответствие количества запрошенных списков и полученных результатов. Пропуск обработки метакласса {meta_class}.")


            # --- Поэтапная синхронизация ---

            # Этап 1: Синхронизация Компаний (в несколько проходов по иерархии)
            logger.info("Начало этапа синхронизации: Компании (по иерархии)")
            company_meta_class = 'ou$company'
            company_config = sync_configs['companies']['configs'][company_meta_class]
            sd_companies_list = sd_entity_lists_raw.get(company_meta_class, [])

            if not sd_companies_list:
                 logger.warning("Список компаний из SD пуст или не был получен. Пропуск синхронизации компаний.")
                 # Инициализируем db_company_uuids пустым, если нет компаний из SD
                 db_company_uuids = set(db_uuids_with_dates.get(company_meta_class, {}).keys())
            else:
                # Создаем набор UUID компаний, которые уже есть в БД
                db_company_uuids = set(db_uuids_with_dates.get(company_meta_class, {}).keys())
                # Создаем словарь SD компаний по UUID для быстрого доступа
                sd_companies_dict = {item.get('UUID'): item for item in sd_companies_list if item and item.get('UUID')} # Добавил проверку на None и наличие UUID в элементе списка

                # Компании, которые еще не обработаны на текущем проходе (их UUID есть в SD списке)
                remaining_companies_uuids = set(sd_companies_dict.keys())
                processed_companies_count = 0
                passes = 0
                max_passes = len(remaining_companies_uuids) + 5 # Ограничиваем количество проходов

                # Набор UUID, успешно обработанных на текущем проходе
                successfully_processed_in_pass = set()

                while remaining_companies_uuids and passes < max_passes:
                    passes += 1
                    logger.info(f"Начало прохода {passes} синхронизации компаний. Осталось обработать: {len(remaining_companies_uuids)}")
                    current_pass_tasks = []
                    companies_to_process_uuids_this_pass = set() # UUID компаний, которые пытаемся обработать в этом проходе

                    # Создаем список UUID для итерации, чтобы можно было безопасно изменять remaining_companies_uuids
                    for company_uuid in list(remaining_companies_uuids):
                        company_data = sd_companies_dict.get(company_uuid)
                        if not company_data:
                            logger.warning(f"Данные для компании с UUID {company_uuid} не найдены в словаре SD данных. Пропускаем.")
                            companies_to_process_uuids_this_pass.add(company_uuid) # Считаем пропущенной для этого прохода
                            continue

                        # Safely get parent_uuid
                        parent_data = company_data.get('parent')
                        # Исправлено: Проверяем, что parent_data является словарем перед вызовом .get('UUID')
                        parent_uuid = parent_data.get('UUID') if isinstance(parent_data, dict) else None

                        # Условие для обработки на этом проходе:
                        # 1. Это верхнеуровневая компания (нет родителя ИЛИ родитель_uuid пустой строкой).
                        # ИЛИ
                        # 2. Родитель этой компании УЖЕ есть в БД (добавлен на предыдущих проходах или уже был там).
                        # Добавил проверку на пустую строку для parent_uuid
                        is_root = parent_uuid is None or parent_uuid == ''
                        parent_in_db = parent_uuid is not None and parent_uuid != '' and parent_uuid in db_company_uuids

                        if is_root or parent_in_db:
                            companies_to_process_uuids_this_pass.add(company_uuid)
                            # Создаем задачу для обработки этой компании
                            current_pass_tasks.append(self.process_and_save_entity(
                                client,
                                company_meta_class,
                                company_data,
                                company_config,
                                db_uuids_with_dates.get(company_meta_class, {}),
                                session_factory,
                                db_company_uuids # Передаем набор, хотя он не будет обновляться внутри process_and_save_entity
                            ))

                    if not companies_to_process_uuids_this_pass:
                        # Если на этом проходе не удалось найти ни одной компании для обработки,
                        # это означает, что осталась циклическая зависимость или ошибка в данных SD.
                        logger.error(f"На проходе {passes} не найдено компаний для обработки. Возможны циклические зависимости или ошибки в данных SD. Оставшиеся UUID: {remaining_companies_uuids}")
                        break # Прерываем цикл

                    logger.info(f"На проходе {passes} будет обработано {len(companies_to_process_uuids_this_pass)} компаний.")

                    # Выполняем задачи для текущего прохода параллельно
                    # asyncio.gather вернет список результатов (UUID или None)
                    results = await asyncio.gather(*current_pass_tasks)

                    # Собираем UUID успешно обработанных компаний из результатов
                    successfully_processed_in_pass = {uuid for uuid in results if uuid is not None}

                    # Обновляем набор компаний, которые теперь считаются в БД
                    db_company_uuids.update(successfully_processed_in_pass)
                    logger.debug(f"После прохода {passes}, набор db_company_uuids обновлен. Теперь содержит {len(db_company_uuids)} UUID.")

                    # Удаляем обработанные компании из списка оставшихся
                    # Удаляем те, которые пытались обработать в этом проходе (независимо от успеха)
                    # Те, что не удалось обработать (вернули None из process_and_save_entity),
                    # останутся в sd_companies_dict и могут быть повторно рассмотрены на следующих проходах,
                    # если их родители появятся в db_company_uuids или пока не исчерпаются проходы.
                    remaining_companies_uuids -= companies_to_process_uuids_this_pass
                    processed_companies_count += len(companies_to_process_uuids_this_pass) # Считаем общее количество попыток обработки
                    logger.info(f"Проход {passes} синхронизации компаний завершен. Успешно сохранено/обновлено: {len(successfully_processed_in_pass)}")

                logger.info(f"На конец этапа 'Компании' в наборе db_company_uuids {len(db_company_uuids)} UUID.")
                if remaining_companies_uuids:
                    logger.warning(f"Не удалось обработать все компании после {passes} проходов. Остались UUID: {remaining_companies_uuids}")


            # Этап 2: Синхронизация Оборудования (Серверы, Рабочие станции, ФР)
            logger.info("Начало этапа синхронизации: Оборудование")
            equipment_meta_classes = sync_configs['equipment']['meta_classes']
            equipment_update_tasks = []

            # Итерируем по метаклассам оборудования
            for meta_class in equipment_meta_classes:
                 # Получаем список сущностей для этого метакласса, если он был успешно получен
                 sd_list = sd_entity_lists_raw.get(meta_class, [])
                 if not sd_list:
                     logger.warning(f"Список сущностей для метакласса {meta_class} пуст или не был получен из SD. Пропуск обработки на этапе 'Оборудование'.")
                     continue

                 # Получаем полную конфигурацию для этого метакласса
                 config = sync_configs['equipment']['configs'].get(meta_class)
                 if not config or not config.get('repo_class') or not config.get('process_func') or not config.get('db_model_class'):
                      logger.warning(f"Неполная конфигурация для метакласса {meta_class} на этапе 'Оборудование'. Пропуск обработки.")
                      continue

                 # Создаем задачи для обработки и сохранения каждой сущности оборудования
                 for sd_item in sd_list:
                      item_uuid = sd_item.get('UUID')
                      if not item_uuid:
                          logger.warning(f"Сущность {meta_class} в списке из SD без UUID. Пропускаем.")
                          continue

                      # Проверка: существует ли владелец этого оборудования в БД?
                      # Это важно, т.к. оборудование привязывается к компании.
                      owner_data = sd_item.get('owner')
                      # Исправлено: Проверяем, что owner_data является словарем перед вызовом .get('UUID')
                      owner_uuid = owner_data.get('UUID') if isinstance(owner_data, dict) else None

                      # Пропускаем сущность оборудования, если у нее нет владельца в SD (owner_uuid is None)
                      # ИЛИ если владелец указан, но не найден в нашем наборе синхронизированных компаний.
                      if owner_uuid is None:
                          logger.warning(f"Сущность {meta_class} {item_uuid} не имеет указанного владельца в ServiceDesk. Пропуск обработки.")
                          continue # Пропускаем эту единицу оборудования

                      if owner_uuid not in db_company_uuids:
                          # Владелец указан, но не найден в БД после этапа синхронизации компаний.
                          logger.warning(f"Владелец компании с UUID {owner_uuid} для сущности {meta_class} {item_uuid} указан в SD, но не найден в БД после этапа компаний. Пропуск обработки этой сущности.")
                          continue # Пропускаем эту единицу оборудования

                      # Если владелец есть в БД (или владелец не указан в SD),
                      # добавляем задачу на обработку
                      equipment_update_tasks.append(self.process_and_save_entity(
                          client,
                          meta_class,
                          sd_item,
                          config,
                          db_uuids_with_dates.get(meta_class, {}), # Словарь дат для этого метакласса оборудования
                          session_factory
                      ))

            # Выполняем все задачи для этапа оборудования параллельно
            if equipment_update_tasks:
                logger.info(f"Запущено {len(equipment_update_tasks)} задач синхронизации для этапа 'Оборудование'.")
                # Собираем результаты, хотя UUID оборудования нам не нужны для дальнейших этапов
                equipment_results = await asyncio.gather(*equipment_update_tasks)
                successfully_processed_equipment_count = len([uuid for uuid in equipment_results if uuid is not None])
                logger.info(f"Этап синхронизации 'Оборудование' завершен. Успешно сохранено/обновлено: {successfully_processed_equipment_count}")
            else:
                logger.info("Нет задач для выполнения на этапе синхронизации 'Оборудование'.")


            # Шаг 3: Удаление сущностей, которых нет в SD - ОТКЛЮЧЕНО
            # TODO: Реализовать логику удаления, сравнивая db_all_uuids с UUIDs из sd_entity_lists_raw.keys()
            # Удаление должно учитывать зависимости (например, удалять оборудование перед компанией).
            # Возможно, потребуется отдельный этап удаления или обработка каскадного удаления в БД.
            logger.info("Пропуск шага удаления сущностей, отсутствующих в SD.")


            logger.info("Инкрементальная синхронизация данных завершена")

    async def process_and_save_entity(
            self,
            client: httpx.AsyncClient,
            meta_class: str,
            sd_item: Dict,
            config: Dict,
            db_entity_dates: Dict[str, datetime.datetime],
            session_factory: async_sessionmaker,
            # Добавляем набор UUID компаний для проверки при создании оборудования
            # Этот аргумент будет использоваться только для логики внутри,
            # сам набор будет обновляться в sync_data_incrementally
            db_company_uuids: Optional[set] = None # Оставил для потенциальных будущих проверок внутри
            ) -> Optional[str]: # Функция теперь может возвращать UUID (str) или None
        """
        Проверяет необходимость обновления сущности по дате изменения,
        получает полные детали (если нужно), обрабатывает и сохраняет в БД.
        Возвращает UUID успешно обработанной сущности или None.
        """
        uuid = sd_item.get('UUID')
        if not uuid:
             logger.warning(f"Сущность {meta_class} в списке из SD без UUID. Пропускаем.")
             return None # Возвращаем None

        sd_last_modified_date_str = sd_item.get('lastModifiedDate')
        if not sd_last_modified_date_str:
             logger.warning(f"Сущность {meta_class} {uuid} не имеет lastModifiedDate в списке из SD. Пропускаем обновление.")
             return None # Возвращаем None

        try:
            sd_last_modified_date = datetime.datetime.strptime(sd_last_modified_date_str, "%Y.%m.%d %H:%M:%S")
        except ValueError:
            logger.error(f"Неверный формат lastModifiedDate для {meta_class} {uuid}: '{sd_last_modified_date_str}'. Пропускаем.")
            return None # Возвращаем None

        # Быстрая проверка даты изменения по собранному словарю из БД
        db_last_modified_date = db_entity_dates.get(uuid)

        needs_update = False
        is_new_entity = False # Флаг для определения, нужно ли создавать или обновлять
        if db_last_modified_date is not None:
            # Сущность существует в БД, сравниваем даты
            if db_last_modified_date < sd_last_modified_date:
                needs_update = True
                logger.debug(f"Сущность {meta_class} {uuid} нуждается в обновлении (дата в SD новее). SD: {sd_last_modified_date}, DB: {db_last_modified_date}")
            else:
                logger.debug(f"Сущность {meta_class} {uuid} актуальна. Пропуск обновления. SD: {sd_last_modified_date}, DB: {db_last_modified_date}")
                return None # Сущность актуальна, пропускаем и возвращаем None

        else:
            # Сущность отсутствует в БД, нужно создать
            needs_update = True
            is_new_entity = True
            logger.debug(f"Сущность {meta_class} {uuid} отсутствует в БД, будет создана")

        if needs_update:
            # Получаем полные детали только если нужно обновить/создать
            full_details = await self.fetch_entity_details(client, uuid, meta_class)
            if not full_details:
                 logger.error(f"Не удалось получить полные детали для {meta_class} {uuid}. Пропускаем сохранение.")
                 return None # Возвращаем None

            # Обрабатываем данные с помощью специфической функции
            if meta_class == 'ou$company':
                 processed_data = await config['process_func'](client, full_details)
            else:
                 processed_data = await config['process_func'](full_details)

            if not processed_data:
                 logger.error(f"Не удалось обработать данные для {meta_class} {uuid}. Пропускаем сохранение.")
                 return None # Возвращаем None

            entity_uuid_to_save = processed_data.get('uuid')
            if not entity_uuid_to_save:
                logger.error(f"Обработанные данные для {meta_class} не содержат UUID. Пропускаем сохранение.")
                return None # Возвращаем None

            # Валидаторы теперь добавляют owner_id и last_modified_date в processed_data
            # Проверка наличия owner_id для оборудования перед созданием
            if is_new_entity and meta_class in ['objectBase$Server', 'objectBase$Workstation', 'objectBase$FR']:
                 owner_uuid = processed_data.get('owner_id')
                 if not owner_uuid:
                      logger.warning(f"Сущность {meta_class} {uuid} не имеет owner_id после обработки. Пропускаем создание.")
                      return None # Пропускаем создание и возвращаем None

                 # Проверку owner_uuid in db_company_uuids делаем на этапе формирования задач в sync_data_incrementally

            async with session_factory() as entity_session:
                try:
                    # Создаем репозиторий, используя эту новую сессию
                    repo = config['repo_class'](entity_session)
                    success = False # Флаг успешного сохранения

                    if is_new_entity: # Если сущность отсутствует в БД
                        created_entity = await repo.create(processed_data)
                        if created_entity:
                             logger.debug(f"Подготовлено к созданию сущность {meta_class} с UUID {entity_uuid_to_save}")
                             success = True # Успешно подготовлена к созданию
                        else:
                             logger.error(f"Репозиторий не вернул созданную сущность для {meta_class} {entity_uuid_to_save}.")

                    else: # Если сущность существует в БД (needs_update=True, is_new_entity=False)
                         updated = await repo.update(entity_uuid_to_save, processed_data)
                         # Методы update репозиториев теперь возвращают True/False/None
                         if updated is True:
                              logger.debug(f"Подготовлено к обновлению сущность {meta_class} с UUID {entity_uuid_to_save}")
                              success = True # Успешно подготовлена к обновлению
                         elif updated is False:
                              logger.warning(f"Обновление сущности {meta_class} с UUID {entity_uuid_to_save} не применилось (запись не найдена?).")
                         else: # updated is None (ошибка в репозитории)
                             logger.error(f"Ошибка в репозитории при обновлении сущности {meta_class} с UUID {entity_uuid_to_save}.")


                    if success:
                         # Если подготовка к сохранению/обновлению прошла успешно, коммитим изменения
                         await entity_session.commit()
                         logger.debug(f"Изменения для сущности {meta_class} {entity_uuid_to_save} закоммичены.")
                         return entity_uuid_to_save # Возвращаем UUID при успешном коммите
                    else:
                         # Если success=False (ошибка или запись не найдена для обновления), откатываем (на всякий случай, хотя при False add/update не было)
                         await entity_session.rollback()
                         logger.debug(f"Изменения для сущности {meta_class} {entity_uuid_to_save} откатаны (т.к. сохранение не было успешным).")
                         return None # Возвращаем None при неуспехе

                except Exception as e:
                    # Если произошла ошибка при сохранении или коммите, откатываем изменения
                    logger.error(f"Ошибка при коммите или неожиданная ошибка при сохранении сущности {meta_class} {entity_uuid_to_save}: {e}", exc_info=True)
                    await entity_session.rollback()
                    logger.debug(f"Изменения для сущности {meta_class} {entity_uuid_to_save} откатаны.")
                    return None # Возвращаем None при ошибке


    # Основной метод синхронизации, вызываемый извне
    # Принимает session_factory
    async def sync_all_data(self, session_factory: async_sessionmaker):
        """
        Запускает инкрементальную синхронизацию всех настроенных метаклассов.
        Использует переданную фабрику сессий.
        """
        # sync_data_incrementally теперь принимает session_factory
        await self.sync_data_incrementally(session_factory)
        logger.info("Полная синхронизация завершена.")


    # Методы для получения данных из БД для фронтенда
    # Принимают session: AsyncSession
    async def get_top_level_companies(self, session: AsyncSession) -> List[Company]:
        """
        Получение верхнеуровневых компаний из БД с подгрузкой связанных данных
        (дочерние компании, серверы, рабочие станции, ФР) для отображения на главной странице.
        Принимает сессию извне.
        """
        try:
            # Используем сессию, переданную в метод
            result = await session.execute(
                select(Company)
                .filter(Company.parent_uuid == None)
                .options(
                    # Рекурсивно подгружаем дочерние компании
                    selectinload(Company.children).selectinload(Company.children), # Подгружаем внуков, если нужно
                    selectinload(Company.children).selectinload(Company.servers),
                    selectinload(Company.children).selectinload(Company.workstations),
                    selectinload(Company.children).selectinload(Company.fiscal_registers),
                    # Подгружаем оборудование для самих верхнеуровневых компаний
                    selectinload(Company.servers),
                    selectinload(Company.workstations),
                    selectinload(Company.fiscal_registers)
                )
            )
            companies = result.scalars().unique().all() # Используем unique() для избежания дубликатов при selectinload
            logger.debug(f"Получено {len(companies)} верхнеуровневых компаний для отображения.")
            return list(companies)
        except SQLAlchemyError as e:
             logger.error(f"Ошибка при получении верхнеуровневых компаний из БД: {e}", exc_info=True)
             return []

    async def get_company_details(self, uuid: str, session: AsyncSession) -> Optional[Company]:
         """Получение деталей компании по UUID с связанными серверами, рабочими станциями и ФР.
          Принимает сессию извне."""
         try:
             # Используем сессию, переданную в метод
             result = await session.execute(
                 select(Company)
                 .filter(Company.uuid == uuid)
                 .options(
                     selectinload(Company.children),
                     selectinload(Company.servers),
                     selectinload(Company.workstations),
                     selectinload(Company.fiscal_registers)
                 )
             )
             company = result.scalars().first()
             logger.debug(f"Поиск деталей компании {uuid} в БД: {'найден' if company else 'не найден'}.")
             return company
         except SQLAlchemyError as e:
              logger.error(f"Ошибка при получении деталей компании {uuid} из БД: {e}", exc_info=True)
              return None

    async def search_entities(self, session: AsyncSession, term: str, show_inactive: bool) -> 'SearchResultResponse':
            """
            Выполняет поиск сущностей (Компании, Серверы, Рабочие станции, ФР) по заданному термину
            в нескольких полях и возвращает результаты.
            """

            search_term_ilike = f"%{term.lower()}%" # Для регистронезависимого поиска с подстроками

            active_company_filter = Company.active_contract == True
            active_equipment_filter = and_(
                Company.uuid == Server.owner_id, # JOIN условие
                active_company_filter # Фильтр по активности владельца
            )
            active_workstation_filter = and_(
                Company.uuid == Workstation.owner_id, # JOIN условие
                active_company_filter # Фильтр по активности владельца
            )
            active_fr_filter = and_(
                Company.uuid == FiscalRegister.owner_id, # JOIN условие
                active_company_filter # Фильтр по активности владельца
            )

            # 1. Поиск компаний
            company_query = select(Company)
            company_filters = [
                Company.title.ilike(search_term_ilike),
                Company.address.ilike(search_term_ilike),
                Company.additional_name.ilike(search_term_ilike),
                Company.uuid.ilike(search_term_ilike) # Поиск по UUID
            ]
            company_query = company_query.filter(or_(*company_filters))
            # Если не показываем неактивные, добавляем фильтр
            if not show_inactive:
                company_query = company_query.filter(active_company_filter)

            if company_filters:
                company_query = company_query.filter(or_(*company_filters)) # Применяем фильтры с OR

            # Ограничиваем количество результатов для каждой категории
            company_results_orm = (await session.execute(company_query.limit(100))).scalars().all()
            companies_list = [CompanySearchResult.model_validate(c) for c in company_results_orm]


            # 2. Поиск серверов
            server_query = select(Server).join(Company, isouter=True)
            server_filters = [
                Server.device_name.ilike(search_term_ilike),
                Server.ip.ilike(search_term_ilike),
                Server.unique_id.ilike(search_term_ilike),
                Server.teamviewer.ilike(search_term_ilike),
                Server.rdp.ilike(search_term_ilike),
                Server.anydesk.ilike(search_term_ilike),
                Server.litemanager.ilike(search_term_ilike),
                Server.description.ilike(search_term_ilike), # Добавляем поиск по описанию
                Server.uuid.ilike(search_term_ilike) # Поиск по UUID
            ]
            server_query = server_query.filter(or_(*server_filters))

            if not show_inactive:
                # Фильтруем только те серверы, у которых есть связанная активная компания
                server_query = server_query.filter(active_equipment_filter)
            else:
                # Если показываем неактивные, мы все равно хотим показывать серверы,
                # у которых owner_id НЕ NULL, даже если компания неактивна.
                # Но при JOIN с isouter=True, если owner_id был NULL, строка все равно вернется.
                # Добавляем фильтр, чтобы owner_id был NOT NULL
                server_query = server_query.filter(Server.owner_id != None)


            server_results_orm = (await session.execute(server_query.limit(100))).scalars().unique().all() # unique() может быть полезно при JOIN
            servers_list = [ServerSearchResult.model_validate(s) for s in server_results_orm]

            # 3. Поиск рабочих станций
            workstation_query = select(Workstation).join(Company, isouter=True)
            workstation_filters = [
                Workstation.device_name.ilike(search_term_ilike),
                Workstation.teamviewer.ilike(search_term_ilike),
                Workstation.anydesk.ilike(search_term_ilike),
                Workstation.litemanager.ilike(search_term_ilike),
                Workstation.description.ilike(search_term_ilike),
                Workstation.uuid.ilike(search_term_ilike)
            ]
            workstation_query = workstation_query.filter(or_(*workstation_filters))

            if not show_inactive:
                workstation_query = workstation_query.filter(active_workstation_filter)
            else:
                workstation_query = workstation_query.filter(Workstation.owner_id != None)


            workstation_results_orm = (await session.execute(workstation_query.limit(100))).scalars().unique().all() # unique() может быть полезно при JOIN
            workstations_list = [WorkstationSearchResult.model_validate(w) for w in workstation_results_orm]

            # 4. Поиск фискальных регистраторов
            fr_query = select(FiscalRegister).join(Company, isouter=True)
            fr_filters = [
                FiscalRegister.rn_kkt.ilike(search_term_ilike),
                FiscalRegister.model_kkt.ilike(search_term_ilike),
                FiscalRegister.fr_serial_number.ilike(search_term_ilike),
                FiscalRegister.fn_number.ilike(search_term_ilike),
                FiscalRegister.legal_name.ilike(search_term_ilike),
                FiscalRegister.uuid.ilike(search_term_ilike)
            ]
            fr_query = fr_query.filter(or_(*fr_filters))

            if not show_inactive:
                fr_query = fr_query.filter(active_fr_filter)
            else:
                fr_query = fr_query.filter(FiscalRegister.owner_id != None)


            fr_results_orm = (await session.execute(fr_query.limit(100))).scalars().unique().all() # unique() может быть полезно при JOIN
            fr_list = [FiscalRegisterSearchResult.model_validate(f) for f in fr_results_orm]

            return SearchResultResponse(
                companies=companies_list,
                servers=servers_list,
                workstations=workstations_list,
                fiscal_registers=fr_list
            )



    # Добавляем метод для получения ФР по владельцу (для использования в будущем)
    # Принимает session: AsyncSession
    async def get_fiscal_registers_by_owner(self, owner_uuid: str, session: AsyncSession) -> List[FiscalRegister]:
        """
        Возвращает список ФР для указанной компании-владельца.
         Принимает сессию извне.
        """
        try:
            # Используем репозиторий и переданную сессию
            fr_repo = FiscalRegisterRepository(session)
            # Метод репозитория get_by_owner_uuid уже возвращает список объектов FiscalRegister
            fr_list = await fr_repo.get_by_owner_uuid(owner_uuid)
            logger.debug(f"Получен список из {len(fr_list)} ФР для владельца {owner_uuid}.")
            return fr_list # Возвращаем список объектов FiscalRegister
        except Exception as e:
             logger.error(f"Ошибка при получении списка ФР для владельца {owner_uuid}: {e}", exc_info=True)
             return []

    # Добавляем метод для получения даты окончания ФН по UUID ФР
    # Принимает session: AsyncSession
    async def get_fn_expire_date_by_fr_uuid(self, fr_uuid: str, session: AsyncSession) -> Optional[datetime.datetime]:
        """
        Возвращает дату окончания срока действия ФН для конкретного ФР по его UUID.
         Принимает сессию извне.
        """
        try:
            # Используем репозиторий и переданную сессию
            fr_repo = FiscalRegisterRepository(session)
            fr = await fr_repo.get_by_uuid(fr_uuid)
            if fr:
                logger.debug(f"Получена дата окончания ФН для ФР {fr_uuid}: {fr.fn_expire_date}")
                return fr.fn_expire_date
            else:
                logger.debug(f"ФР с UUID {fr_uuid} не найден для получения даты окончания ФН.")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении даты окончания ФН для ФР {fr_uuid}: {e}", exc_info=True)
            return None


    # Заглушка для метода синхронизации данных с FTP
    # Принимает session_factory, так как будет управлять сессиями внутри себя
    async def sync_ftp_data(self, session_factory: async_sessionmaker):
        """
        Заглушка: Метод для синхронизации данных с FTP.
        """
        logger.info("Заглушка: Запущена синхронизация данных с FTP.")
        # TODO: Реализовать логику получения файлов с FTP
        # TODO: Распарсить JSON
        # TODO: Сопоставить данные с сущностями в БД (ФР, Workstation)
        # TODO: Вызвать методы репозиториев для обновления (например, owner_id для ФР)

        # Пример: Получить список всех ФР и вызвать заглушку присвоения владельца
        # async with session_factory() as session:
        #      fr_repo = FiscalRegisterRepository(session)
        #      fr_list_all = await fr_repo.get_all() # Предполагается наличие async def get_all(self) в FRRepository
        #      for fr in fr_list_all:
        #           # Имитация получения данных с FTP для этого ФР
        #           fake_ftp_data = {"fr_serial": fr.fr_serial_number, "company_inn": "какой-то ИНН"}
        #           # Метод репозитория assign_owner_from_ftp_data должен принимать сессию или быть вызван с репозиторием, созданным с этой сессией
        #           await fr_repo.assign_owner_from_ftp_data(fr.uuid, fake_ftp_data)
        #      await session.commit() # Коммит после обработки всех ФР из FTP данных

        logger.info("Заглушка: Синхронизация данных с FTP завершена.")
        pass # Убрать pass после реализации
