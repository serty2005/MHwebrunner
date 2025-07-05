from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from models import Company, Server, Workstation
from typing import Optional, List
import logging

logger = logging.getLogger("ServiceDeskLogger")

class CompanyRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, company_data: dict) -> Optional[Company]:
        try:
            company = Company(
                uuid=company_data['uuid'],
                title=company_data['title'],
                address=company_data['address'],
                active_contract=company_data['active_contract'],
                last_modified_date=company_data['last_modified_date'],
                additional_name=company_data['additional_name'],
                parent_uuid=company_data['parent_uuid']
            )
            self.session.add(company)
            self.session.commit()
            return company
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании компании: {e}")
            self.session.rollback()
            return None

    def update(self, uuid: str, company_data: dict) -> Optional[Company]:
        try:
            company = self.session.query(Company).filter(Company.uuid == uuid).first()
            if company:
                company.title = company_data['title']
                company.address = company_data['address']
                company.active_contract = company_data['active_contract']
                company.last_modified_date = company_data['last_modified_date']
                company.additional_name = company_data['additional_name']
                company.parent_uuid = company_data['parent_uuid']
                self.session.commit()
                return company
            return None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении компании: {e}")
            self.session.rollback()
            return None

    def delete(self, uuid: str) -> bool:
        try:
            company = self.session.query(Company).filter(Company.uuid == uuid).first()
            if company:
                self.session.delete(company)
                self.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении компании: {e}")
            self.session.rollback()
            return False

    def get_by_uuid(self, uuid: str) -> Optional[Company]:
        try:
            return self.session.query(Company).filter(Company.uuid == uuid).first()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении компании: {e}")
            return None

    def get_all(self) -> List[Company]:
        try:
            return self.session.query(Company).all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении списка компаний: {e}")
            return []

class ServerRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, server_data: dict, owner_uuid: str) -> Optional[Server]:
        try:
            server = Server(
                uuid=server_data.get('UUID'),
                unique_id=server_data.get('unique_id'),
                teamviewer=server_data.get('teamviewer'),
                rdp=server_data.get('rdp'),
                anydesk=server_data.get('anydesk'),
                ip=server_data.get('ip'),
                device_name=server_data.get('device_name'),
                last_modified_date=server_data.get('lastModifiedDate'),
                litemanager=server_data.get('litemanager'),
                iiko_version=server_data.get('iiko_version'),
                description=server_data.get('description'),
                owner_id=owner_uuid
            )
            self.session.add(server)
            self.session.commit()
            return server
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании сервера: {e}")
            self.session.rollback()
            return None

    def update(self, uuid: str, server_data: dict) -> Optional[Server]:
        try:
            server = self.session.query(Server).filter(Server.uuid == uuid).first()
            if server:
                for key, value in server_data.items():
                    if hasattr(server, key):
                        setattr(server, key, value)
                self.session.commit()
                return server
            return None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении сервера: {e}")
            self.session.rollback()
            return None

    def get_by_uuid(self, uuid: str) -> Optional[Server]:
        try:
            return self.session.query(Server).filter(Server.uuid == uuid).first()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении сервера: {e}")
            return None

class WorkstationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, workstation_data: dict, owner_uuid: str) -> Optional[Workstation]:
        try:
            workstation = Workstation(
                uuid=workstation_data.get('UUID'),
                teamviewer=workstation_data.get('teamviewer'),
                anydesk=workstation_data.get('anydesk'),
                device_name=workstation_data.get('device_name'),
                last_modified_date=workstation_data.get('lastModifiedDate'),
                litemanager=workstation_data.get('litemanager'),
                description=workstation_data.get('description'),
                owner_id=owner_uuid
            )
            self.session.add(workstation)
            self.session.commit()
            return workstation
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при создании рабочей станции: {e}")
            self.session.rollback()
            return None

    def update(self, uuid: str, workstation_data: dict) -> Optional[Workstation]:
        try:
            workstation = self.session.query(Workstation).filter(Workstation.uuid == uuid).first()
            if workstation:
                for key, value in workstation_data.items():
                    if hasattr(workstation, key):
                        setattr(workstation, key, value)
                self.session.commit()
                return workstation
            return None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении рабочей станции: {e}")
            self.session.rollback()
            return None

    def get_by_uuid(self, uuid: str) -> Optional[Workstation]:
        try:
            return self.session.query(Workstation).filter(Workstation.uuid == uuid).first()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении рабочей станции: {e}")
            return None
