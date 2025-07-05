from repositories import CompanyRepository, ServerRepository, WorkstationRepository
from sqlalchemy.orm import Session
import httpx
import asyncio
from typing import Optional, List, Dict
import logging
from aiolimiter import AsyncLimiter
import os
from data_validator import clearify_server_data, clearify_pos_data
import datetime

logger = logging.getLogger("ServiceDeskLogger")
limiter = AsyncLimiter(45, 1)

class ServiceDeskService:
    def __init__(self, session: Session):
        self.session = session
        self.company_repo = CompanyRepository(session)
        self.server_repo = ServerRepository(session)
        self.workstation_repo = WorkstationRepository(session)
        self.base_api_url = f"{os.getenv('BASE_URL')}/services/rest/"
        self.access_key = os.getenv("SDKEY")

    async def check_agreement_active(self, client: httpx.AsyncClient, agreement_data: dict) -> bool:
        """Проверка активности контракта"""
        agreement_url = f"{self.base_api_url}get/{agreement_data['UUID']}"
        agreement_params = {
            "accessKey": self.access_key,
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
            try:
                agreement_info = response.json()
                logger.debug(f"Статус контракта: {agreement_info['state']}")
                return agreement_info['state'] == 'active'
            except Exception as e:
                logger.error(f"Ошибка при разборе ответа контракта {agreement_data['UUID']}: {e}")
                return False
        return False
        
    async def sync_company(self, client: httpx.AsyncClient, company_data: dict) -> Optional[Dict]:
        """Синхронизация данных компании"""
        # Проверка активности контракта
        active_contract = False
        for agreement_data in company_data.get('recipientAgreements', []):
            if agreement_data['metaClass'] == 'agreement$agreement':
                is_active = await self.check_agreement_active(client, agreement_data)
                if is_active:
                    active_contract = True
                    break

        # Подготовка данных компании
        company_info = {
            'uuid': company_data['UUID'],
            'title': company_data['title'],
            'address': company_data.get('adress'),
            'last_modified_date': datetime.datetime.strptime(company_data['lastModifiedDate'], "%Y.%m.%d %H:%M:%S"),
            'additional_name': company_data.get('additionalName'),
            'parent_uuid': company_data.get('parent', {}).get('UUID') if company_data.get('parent') else None,
            'active_contract': active_contract
        }

        existing_company = self.company_repo.get_by_uuid(company_data['UUID'])
        if existing_company:
            if existing_company.last_modified_date != company_info['last_modified_date']:
                return self.company_repo.update(company_data['UUID'], company_info)
            return existing_company
        else:
            return self.company_repo.create(company_info)

    async def sync_server(self, equipment_data: dict, company_uuid: str) -> Optional[Dict]:
        """Синхронизация данных сервера"""
        try:
            server = await self.server_repo.get_by_uuid(equipment_data['UUID'])
            # Очистка и валидация данных сервера
            cleaned_data = await clearify_server_data(equipment_data)
            if server:
                return await self.server_repo.update(equipment_data['UUID'], cleaned_data)
            return await self.server_repo.create(cleaned_data, company_uuid)
        except Exception as e:
            logger.error(f"Ошибка при синхронизации сервера {equipment_data.get('UUID')}: {e}")
            return None

    async def sync_workstation(self, equipment_data: dict, company_uuid: str) -> Optional[Dict]:
        """Синхронизация данных рабочей станции"""
        try:
            workstation = await self.workstation_repo.get_by_uuid(equipment_data['UUID'])
            # Очистка и валидация данных рабочей станции
            cleaned_data = await clearify_pos_data(equipment_data)
            if workstation:
                return await self.workstation_repo.update(equipment_data['UUID'], cleaned_data)
            return await self.workstation_repo.create(cleaned_data, company_uuid)
        except Exception as e:
            logger.error(f"Ошибка при синхронизации рабочей станции {equipment_data.get('UUID')}: {e}")
            return None

    async def fetch_companies(self) -> List[Dict]:
        """Получение списка компаний из ServiceDesk"""
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            url = f"{self.base_api_url}find/ou$company"
            payload = {
                "accessKey": self.access_key,
                "attrs": "adress,UUID,title,lastModifiedDate,additionalName,parent,recipientAgreements,KEsInUse"
            }
            try:
                async with limiter:
                    response = await client.post(url, params=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Ошибка при получении списка компаний: {e}")
                return []

    async def sync_all_data(self):
        """Синхронизация всех данных"""
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            companies = await self.fetch_companies()
            for company_data in companies:
                company = await self.sync_company(client, company_data)
                if company:
                    for equipment_data in company_data.get('KEsInUse', []):
                        if equipment_data['metaClass'] == 'objectBase$Server':
                            await self.sync_server(equipment_data, company.uuid)
                        elif equipment_data['metaClass'] == 'objectBase$Workstation':
                            await self.sync_workstation(equipment_data, company.uuid)
                        elif equipment_data['metaClass'] == 'objectBase$FR':
                            # TODO: Добавить обработку ФР когда будет готов репозиторий
                            logger.info(f"Пропуск ФР {equipment_data['UUID']} - функционал в разработке")
                await asyncio.sleep(0.1)  # Небольшая пауза между обработкой компаний
