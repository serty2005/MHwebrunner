from sqlalchemy import create_engine, Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
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
    parent = relationship("Company", remote_side=[uuid], backref="children")
    servers = relationship("Server", back_populates="owner")
    workstations = relationship("Workstation", back_populates="owner")

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
    cabinet_link = Column(String)  
    device_name = Column(String)
    last_modified_date = Column(DateTime)
    litemanager = Column(String)
    iiko_version = Column(String)
    description = Column(String)
    owner_id = Column(String, ForeignKey('companies.uuid'))
    owner = relationship("Company", back_populates="servers")

# Модель для рабочей станции
class Workstation(Base):
    __tablename__ = 'workstations'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='objectBase$Workstation')
    commentary = Column(String)
    teamviewer = Column(String)
    anydesk = Column(String)
    litemanager = Column(String)
    device_name = Column(String)
    last_modified_date = Column(DateTime)
    uuid = Column(String, unique=True)
    owner_id = Column(String, ForeignKey('companies.uuid'))
    owner = relationship("Company", back_populates="workstations")

# Настройка подключения к базе данных
#DATABASE_URL = "sqlite:///./test.db"
#engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
#Base.metadata.create_all(bind=engine)
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Пример использования сессии для добавления данных
if __name__ == "__main__":
    session = AsyncSessionLocal()
    new_company = Company()
    session.add(new_company)
    session.commit()
    session.close()