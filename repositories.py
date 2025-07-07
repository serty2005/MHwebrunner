from sqlalchemy import select, update, delete # Импортируем delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from models import Company, Server, Workstation, FiscalRegister
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("ServiceDeskLogger")

class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company_data: dict) -> Optional[Company]:
        """Создает новую запись о компании в БД."""
        try:
            # Проверяем наличие обязательного поля UUID
            if not company_data.get('uuid'):
                 logger.error("Попытка создания компании без UUID.")
                 # Нет необходимости в rollback, если сессия только создана и ничего не добавлено
                 return None

            company = Company(
                uuid=company_data.get('uuid'),
                title=company_data.get('title'),
                address=company_data.get('address'),
                active_contract=company_data.get('active_contract'),
                last_modified_date=company_data.get('last_modified_date'),
                additional_name=company_data.get('additional_name'),
                parent_uuid=company_data.get('parent_uuid')
            )
            self.session.add(company)
            # Коммит происходит в сервисе после успешной обработки сущности
            # await self.session.commit()
            logger.debug(f"Подготовлено к созданию компания с UUID: {company.uuid}")
            return company
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании компании с данными {company_data.get('uuid')}: {e}", exc_info=True)
            # Откат происходит в сервисе при ошибке сохранения
            # await self.session.rollback()
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при создании компании с данными {company_data.get('uuid')}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def update(self, uuid: str, company_data: dict) -> Optional[Company]:
        """Обновляет запись о компании в БД по UUID."""
        try:
            # Используем асинхронное обновление напрямую
            result = await self.session.execute(
                update(Company)
                .where(Company.uuid == uuid)
                # Используем только те ключи из company_data, которые есть в модели Company
                # Это предотвратит ошибки, если processed_data содержит лишние ключи
                .values({k: v for k, v in company_data.items() if hasattr(Company, k)})
            )
            # Коммит происходит в сервисе после успешной обработки сущности
            # await self.session.commit()

            if result.rowcount > 0:
                logger.debug(f"Подготовлено к обновлению компания с UUID: {uuid}")
                # Возвращаем обновленный объект (делаем отдельный запрос, если нужно)
                # Для простоты, пока не возвращаем объект сразу, т.к. коммит не здесь.
                # Сервис может получить его после коммита, если потребуется.
                return True # Указываем, что обновление было применено к хотя бы одной строке
            else:
                 logger.warning(f"Попытка обновить компанию с UUID {uuid}, но запись не найдена.")
                 return False # Указываем, что запись не найдена для обновления
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении компании {uuid}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return None # Возвращаем None или False, чтобы сервис знал об ошибке
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при обновлении компании {uuid}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def delete(self, uuid: str) -> bool:
        """Удаляет запись о компании по UUID."""
        try:
            # Используем асинхронное удаление
            result = await self.session.execute(delete(Company).where(Company.uuid == uuid))
            # Коммит происходит в сервисе
            # await self.session.commit()
            if result.rowcount > 0:
                logger.debug(f"Подготовлено к удалению компания с UUID: {uuid}")
                return True
            else:
                logger.debug(f"Попытка удалить компанию с UUID {uuid}, но запись не найдена.")
                return False
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении компании {uuid}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return False
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при удалении компании {uuid}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return False


    async def get_by_uuid(self, uuid: str) -> Optional[Company]:
        """Получает компанию по ее UUID."""
        try:
            result = await self.session.execute(select(Company).filter(Company.uuid == uuid))
            company = result.scalars().first()
            # Логгируем как debug, если объект не найден, это не ошибка
            # if company:
            #      logger.debug(f"Найден компания по UUID: {uuid}")
            # else:
            #      logger.debug(f"Компания с UUID {uuid} не найдена в БД.")
            return company
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении компании по UUID {uuid}: {e}", exc_info=True)
            return None


    async def get_all(self) -> List[Company]:
        """Получает список всех компаний."""
        try:
            result = await self.session.execute(select(Company))
            companies = result.scalars().all()
            logger.debug(f"Получено {len(companies)} компаний из БД.")
            return list(companies)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении списка компаний из БД: {e}", exc_info=True)
            return []


class ServerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, server_data: dict) -> Optional[Server]:
        """Создает новую запись о сервере в БД."""
        try:
            # Проверяем наличие обязательных полей UUID и owner_id
            if not server_data.get('uuid'):
                 logger.error("Попытка создания сервера без UUID.")
                 return None
            owner_uuid = server_data.get('owner_id')
            if not owner_uuid:
                 logger.warning(f"Попытка создания сервера {server_data.get('uuid')} без owner_id в данных. Пропускаем создание.")
                 return None

            server = Server(
                uuid=server_data.get('uuid'),
                unique_id=server_data.get('unique_id'),
                teamviewer=server_data.get('teamviewer'),
                rdp=server_data.get('rdp'),
                anydesk=server_data.get('anydesk'),
                ip=server_data.get('ip'),
                cabinet_link=server_data.get('cabinet_link'),
                device_name=server_data.get('device_name'),
                last_modified_date=server_data.get('last_modified_date'), # Используем snake_case как в модели
                litemanager=server_data.get('litemanager'),
                iiko_version=server_data.get('iiko_version'),
                description=server_data.get('description'),
                owner_id=owner_uuid
            )
            self.session.add(server)
            # Коммит происходит в сервисе
            # await self.session.commit()
            logger.debug(f"Подготовлено к созданию сервер с UUID: {server.uuid}, владелец: {server.owner_id}")
            return server
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании сервера {server_data.get('uuid')}: {e}", exc_info=True)
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при создании сервера {server_data.get('uuid')}: {e}", exc_info=True)
             return None


    async def update(self, uuid: str, server_data: dict) -> Optional[Server]:
        """Обновляет запись о сервере в БД по UUID."""
        try:
            # Используем асинхронное обновление напрямую
            result = await self.session.execute(
                update(Server)
                .where(Server.uuid == uuid)
                 # Используем только те ключи из server_data, которые есть в модели Server
                .values({k: v for k, v in server_data.items() if hasattr(Server, k) and k != 'uuid'})
            )
            # Коммит происходит в сервисе
            # await self.session.commit()

            if result.rowcount > 0:
                logger.debug(f"Подготовлено к обновлению сервер с UUID: {uuid}")
                return True # Указываем, что обновление было применено
            else:
                 logger.warning(f"Попытка обновить сервер с UUID {uuid}, но запись не найдена.")
                 return False # Указываем, что запись не найдена для обновления
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении сервера {uuid}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при обновлении сервера {uuid}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def get_by_uuid(self, uuid: str) -> Optional[Server]:
        """Получает сервер по его UUID."""
        try:
            result = await self.session.execute(select(Server).filter(Server.uuid == uuid))
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении сервера по UUID {uuid}: {e}", exc_info=True)
            return None

class WorkstationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, workstation_data: dict) -> Optional[Workstation]:
        """Создает новую запись о рабочей станции в БД."""
        try:
             # Проверяем наличие обязательных полей UUID и owner_id
            if not workstation_data.get('uuid'):
                 logger.error("Попытка создания рабочей станции без UUID.")
                 return None
            owner_uuid=workstation_data.get('owner_id')
            if not owner_uuid:
                 logger.warning(f"Попытка создания рабочей станции {workstation_data.get('uuid')} без owner_id. Пропускаем создание.")
                 return None

            workstation = Workstation(
                uuid=workstation_data.get('uuid'),
                teamviewer=workstation_data.get('teamviewer'),
                anydesk=workstation_data.get('anydesk'),
                device_name=workstation_data.get('device_name'),
                last_modified_date=workstation_data.get('last_modified_date'), # Используем snake_case
                litemanager=workstation_data.get('litemanager'),
                description=workstation_data.get('description'), # Commentary из SD
                owner_id=owner_uuid # Берем owner_id из processed_data
            )
            self.session.add(workstation)
            # Коммит происходит в сервисе
            # await self.session.commit()
            logger.debug(f"Подготовлено к созданию рабочая станция с UUID: {workstation.uuid}, владелец: {workstation.owner_id}")
            return workstation
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании рабочей станции {workstation_data.get('uuid')}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при создании рабочей станции {workstation_data.get('uuid')}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def update(self, uuid: str, workstation_data: dict) -> Optional[Workstation]:
        """Обновляет запись о рабочей станции в БД по UUID."""
        try:
            # Используем асинхронное обновление напрямую
            result = await self.session.execute(
                update(Workstation)
                .where(Workstation.uuid == uuid)
                 # Используем только те ключи из workstation_data, которые есть в модели Workstation
                .values({k: v for k, v in workstation_data.items() if hasattr(Workstation, k) and k != 'uuid'})
            )
            # Коммит происходит в сервисе
            # await self.session.commit()

            if result.rowcount > 0:
                logger.debug(f"Подготовлено к обновлению рабочая станция с UUID: {uuid}")
                return True # Указываем, что обновление было применено
            else:
                 logger.warning(f"Попытка обновить рабочую станцию с UUID {uuid}, но запись не найдена.")
                 return False # Указываем, что запись не найдена для обновления
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении рабочей станции {uuid}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при обновлении рабочей станции {uuid}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def get_by_uuid(self, uuid: str) -> Optional[Workstation]:
        """Получает рабочую станцию по ее UUID."""
        try:
            # Исправлено на асинхронный запрос
            result = await self.session.execute(select(Workstation).filter(Workstation.uuid == uuid))
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении рабочей станции по UUID {uuid}: {e}", exc_info=True)
            return None

class FiscalRegisterRepository:
    def __init__(self, session: AsyncSession): # Принимаем асинхронную сессию
        self.session = session

    async def create(self, fr_data: dict) -> Optional[FiscalRegister]:
        """Создает новую запись о фискальном регистраторе в БД."""
        try:
            # Проверяем наличие обязательных полей UUID и owner_id
            if not fr_data.get('uuid'):
                 logger.error("Попытка создания ФР без UUID.")
                 return None
            owner_uuid = fr_data.get('owner_id')
            if not owner_uuid:
                 logger.warning(f"Попытка создания ФР {fr_data.get('uuid')} без owner_id. Пропускаем создание.")
                 return None

            # Создаем объект модели, используя данные из словаря
            # В fr_data уже есть owner_id после process_fr_data
            fr = FiscalRegister(
                uuid=fr_data.get('uuid'),
                model_kkt=fr_data.get('model_kkt'),
                ffd=fr_data.get('ffd'),
                fr_downloader=fr_data.get('fr_downloader'),
                rn_kkt=fr_data.get('rn_kkt'),
                legal_name=fr_data.get('legal_name'),
                fr_serial_number=fr_data.get('fr_serial_number'),
                fn_number=fr_data.get('fn_number'),
                kkt_reg_date=fr_data.get('kkt_reg_date'), # Даты уже в формате datetime после валидатора
                fn_expire_date=fr_data.get('fn_expire_date'),
                last_modified_date=fr_data.get('last_modified_date'), # Дата последнего изменения
                owner_id=owner_uuid
            )
            self.session.add(fr)
            # Коммит происходит в сервисе
            # await self.session.commit()
            logger.debug(f"Подготовлено к созданию ФР с UUID: {fr.uuid}, владелец: {fr.owner_id}")
            return fr
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании ФР {fr_data.get('uuid')}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при создании ФР {fr_data.get('uuid')}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def update(self, uuid: str, fr_data: dict) -> Optional[FiscalRegister]:
        """Обновляет запись о фискальном регистраторе в БД по UUID."""
        try:
            # Используем асинхронное обновление напрямую
            result = await self.session.execute(
                update(FiscalRegister)
                .where(FiscalRegister.uuid == uuid)
                 # Используем только те ключи из fr_data, которые есть в модели FiscalRegister
                .values({k: v for k, v in fr_data.items() if hasattr(FiscalRegister, k) and k != 'uuid'})
            )
            # Коммит происходит в сервисе
            # await self.session.commit() # Асинхронный коммит

            if result.rowcount > 0:
                logger.debug(f"Подготовлено к обновлению ФР с UUID: {uuid}")
                # Возвращаем True, т.к. коммит не здесь
                return True
            else:
                 logger.warning(f"Попытка обновить ФР с UUID {uuid}, но запись не найдена.")
                 return False
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении ФР {uuid}: {e}", exc_info=True)
            # Откат происходит в сервисе
            # await self.session.rollback()
            return None
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при обновлении ФР {uuid}: {e}", exc_info=True)
             # Откат происходит в сервисе
             return None


    async def get_by_uuid(self, uuid: str) -> Optional[FiscalRegister]:
        """Получает фискальный регистратор по его UUID."""
        try:
            result = await self.session.execute(select(FiscalRegister).filter(FiscalRegister.uuid == uuid))
            fr = result.scalars().first()
            # Логгируем как debug, если объект не найден, это не ошибка
            # if fr:
            #      logger.debug(f"Найден ФР по UUID: {uuid}")
            # else:
            #      logger.debug(f"ФР с UUID {uuid} не найден в БД.")
            return fr
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении ФР по UUID {uuid}: {e}", exc_info=True)
            return None


    async def get_by_owner_uuid(self, owner_uuid: str) -> List[FiscalRegister]:
        """
        Возвращает список фискальных регистраторов для указанной компании-владельца.
        """
        try:
            result = await self.session.execute(
                select(FiscalRegister)
                .filter(FiscalRegister.owner_id == owner_uuid)
            )
            fiscal_registers = result.scalars().all()
            logger.debug(f"Найдено {len(fiscal_registers)} ФР для владельца {owner_uuid}")
            return list(fiscal_registers) # Возвращаем список объектов FiscalRegister
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении ФР для владельца {owner_uuid}: {e}", exc_info=True)
            return []


    # Заглушка для метода присвоения владельца по данным с FTP
    async def assign_owner_from_ftp_data(self, fr_uuid: str, ftp_data: Dict[str, Any]) -> bool:
        """
        Заглушка: Присваивает или обновляет владельца ФР на основе данных с FTP.
        """
        logger.info(f"Заглушка: Вызван метод assign_owner_from_ftp_data для ФР {fr_uuid}.")
        logger.debug(f"Получены FTP данные: {ftp_data}")

        # TODO: Реализовать логику сопоставления данных с ФР и обновления owner_id
        # Пример: найти компанию по какому-то полю из ftp_data (например, ИНН)
        # и обновить owner_id ФР.
        # company = await self.session.execute(select(Company).filter(Company.inn == ftp_data.get('company_inn'))).scalars().first()
        # if company:
        #     fr = await self.get_by_uuid(fr_uuid) # Нужно получить ФР в этой же сессии
        #     if fr and fr.owner_id != company.uuid:
        #         fr.owner_id = company.uuid
        #         # Коммит или flush здесь или в вызывающем коде, в зависимости от контекста
        #         # await self.session.commit()
        #         logger.info(f"Заглушка: Владелец ФР {fr_uuid} обновлен на компанию {company.uuid}.")
        #         return True
        #     elif fr:
        #         logger.debug(f"Заглушка: Владелец ФР {fr_uuid} уже установлен верно.")
        #         return False # Владелец уже правильный или не найден ФР
        # else:
        #     logger.warning(f"Заглушка: Компания с INN {ftp_data.get('company_inn')} не найдена для ФР {fr_uuid}.")
        #     return False # Компания не найдена

        # Пока просто возвращаем False, так как логика не реализована
        return False