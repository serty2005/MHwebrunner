from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import uuid

# Создаем базовый класс для модели данных
Base = declarative_base()

# Модель для компании
class Company(Base):
    __tablename__ = 'companies'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='ou$company')
    address = Column(String)
    uuid = Column(String, unique=True)
    title = Column(String)
    active_contract = Column(Boolean)
    last_modified_date = Column(DateTime)
    additional_name = Column(String)
    parent_uuid = Column(String, ForeignKey('companies.uuid'), nullable=True)
    parent = relationship("Company", remote_side=[uuid])
 

# Модель для контракта
class Agreement(Base):
    __tablename__ = 'agreements'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    uuid = Column(String)
    title = Column(String)
    meta_class = Column(String)
    state = Column(Boolean)
    company_id = Column(String, ForeignKey('companies.uuid'))
    company = relationship("Company", back_populates="agreements")

Company.agreements = relationship("Agreement", order_by=Agreement.id, back_populates="company")

# Модель для оборудования
class Equipment(Base):
    __tablename__ = 'equipment'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    uuid = Column(String, unique=True)
    title = Column(String)
    meta_class = Column(String)
    company_id = Column(String, ForeignKey('companies.uuid'))
    company = relationship("Company", back_populates="equipment")

Company.equipment = relationship("Equipment", order_by=Equipment.id, back_populates="company")

# Модель для сервера
class Server(Base):
    __tablename__ = 'servers'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='objectBase$Server')
    unique_id = Column(String)
    teamviewer = Column(String)
    rdp = Column(String)
    anydesk = Column(String)
    uuid = Column(String, unique=True)
    ip = Column(String)
    server_type = Column(String)
    cabinet_link = Column(String)
    owner_id = Column(String, ForeignKey('companies.uuid'))
    device_name = Column(String)
    last_modified_date = Column(DateTime)
    cloud = Column(Boolean)
    iiko_version = Column(String)
    owner = relationship("Company")

# Модель для рабочей станции
class Workstation(Base):
    __tablename__ = 'workstations'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='objectBase$Workstation')
    commentary = Column(String)
    teamviewer = Column(String)
    anydesk = Column(String)
    owner_id = Column(String, ForeignKey('companies.uuid'))
    device_name = Column(String)
    last_modified_date = Column(DateTime)
    uuid = Column(String, unique=True)
    owner = relationship("Company")

# Настройка подключения к базе данных
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Пример использования сессии для добавления данных
if __name__ == "__main__":
    session = SessionLocal()
    new_company = Company()
    session.add(new_company)
    session.commit()
    session.close()