from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, select
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import uuid
import asyncio
# import uuid # Импортировано выше
import logging
import os # Импортируем os для переменных окружения

logger = logging.getLogger("ServiceDeskLogger")
# Создаем базовый класс для модели данных
Base = declarative_base()

# Модель для компании
class Company(Base):
    __tablename__ = 'companies'
    # Уникальный ID записи в нашей БД (генерируется локально)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # meta_class из SD (для информации, не FK)
    meta_class = Column(String, default='ou$company')
    address = Column(String)
    # UUID из ServiceDesk (используется как FK для дочерних компаний и оборудования)
    uuid = Column(String, unique=True)
    title = Column(String)
    # Признак активного контракта (определяется при синхронизации)
    active_contract = Column(Boolean)
    # Дата последнего изменения в SD
    last_modified_date = Column(DateTime)
    additional_name = Column(String)
    # FK на UUID родительской компании
    parent_uuid = Column(String, ForeignKey('companies.uuid'), nullable=True)
    # Связь с родительской компанией
    parent = relationship("Company", remote_side=[uuid], backref="children")
    # Связи с оборудованием, owned by this company
    servers = relationship("Server", back_populates="owner")
    workstations = relationship("Workstation", back_populates="owner")
    fiscal_registers = relationship("FiscalRegister", back_populates="owner")

    # Добавляем __repr__ для удобного отладочного вывода
    def __repr__(self):
        return f"<Company(uuid='{self.uuid}', title='{self.title}', active_contract={self.active_contract}, parent_uuid='{self.parent_uuid}')>"


# Модель для сервера
class Server(Base):
    __tablename__ = 'servers'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='objectBase$Server')
    unique_id = Column(String)
    teamviewer = Column(String)
    rdp = Column(String)
    anydesk = Column(String)
    uuid = Column(String, unique=True) # UUID из SD
    ip = Column(String)
    cabinet_link = Column(String)
    device_name = Column(String)
    last_modified_date = Column(DateTime)
    litemanager = Column(String)
    iiko_version = Column(String)
    description = Column(String) # Объединенное описание из SD
    owner_id = Column(String, ForeignKey('companies.uuid')) # FK на UUID компании-владельца
    owner = relationship("Company", back_populates="servers")

    def __repr__(self):
        return f"<Server(uuid='{self.uuid}', device_name='{self.device_name}', owner_id='{self.owner_id}')>"


# Модель для рабочей станции
class Workstation(Base):
    __tablename__ = 'workstations'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='objectBase$Workstation')
    # Commentary из SD теперь маппится в description
    # commentary = Column(String) # Это поле больше не нужно, используем description
    teamviewer = Column(String)
    anydesk = Column(String)
    litemanager = Column(String)
    device_name = Column(String)
    last_modified_date = Column(DateTime)
    description = Column(String) # Commentary из SD
    uuid = Column(String, unique=True) # UUID из SD
    owner_id = Column(String, ForeignKey('companies.uuid')) # FK на UUID компании-владельца
    owner = relationship("Company", back_populates="workstations")

    def __repr__(self):
        return f"<Workstation(uuid='{self.uuid}', device_name='{self.device_name}', owner_id='{self.owner_id}')>"


class FiscalRegister(Base):
    __tablename__ = 'fiscal_registers'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meta_class = Column(String, default='objectBase$FR')
    uuid = Column(String, unique=True) # UUID из SD
    model_kkt = Column(String)
    ffd = Column(String)
    fr_downloader = Column(String)
    rn_kkt = Column(String) # Регномер ККТ
    legal_name = Column(String) # Юр. лицо из ФР
    fr_serial_number = Column(String) # Заводской номер ФР
    fn_number = Column(String) # Номер ФН
    kkt_reg_date = Column(DateTime, nullable=True) # Дата регистрации ККТ
    fn_expire_date = Column(DateTime, nullable=True) # Дата окончания ФН
    last_modified_date = Column(DateTime) # Дата последнего изменения в SD
    owner_id = Column(String, ForeignKey('companies.uuid')) # FK на UUID компании-владельца
    owner = relationship("Company", back_populates="fiscal_registers")

    def __repr__(self):
        return f"<FiscalRegister(uuid='{self.uuid}', rn_kkt='{self.rn_kkt}', owner_id='{self.owner_id}')>"


# Получаем URL базы данных из переменных окружения
# Убедитесь, что DATABASE_URL установлен (например, в .env файле)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(DATABASE_URL)
# Создаем фабрику асинхронных сессий
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False) # expire_on_commit=False полезно для работы с объектами после коммита

async def check_db_connection(retries: int = 5, delay: int = 3):
    """
    Проверяет подключение к базе данных с заданным количеством повторных попыток
    и задержкой между ними.
    При успешном подключении возвращает True.
    При неудаче после всех попыток генерирует исключение.
    """
    logger.info(f"Проверка подключения к базе данных по URL: {DATABASE_URL}")
    for i in range(retries):
        try:
            # Попытка установить соединение
            async with engine.connect() as connection:
                # Если соединение установлено, выполнить простую проверку (например, SELECT 1)
                # Это гарантирует, что соединение действительно работает
                await connection.execute(select(1))
                logger.info("Подключение к базе данных успешно установлено.")
                return True # Подключение успешно

        except (OperationalError, SQLAlchemyError) as e:
            # Логгируем ошибку подключения
            logger.warning(f"Попытка {i + 1}/{retries} подключения к БД не удалась: {e}")
            if i < retries - 1:
                # Если есть еще попытки, ждем перед следующей
                logger.info(f"Повторная попытка через {delay} секунд...")
                await asyncio.sleep(delay)
            else:
                # Если попытки исчерпаны, логгируем критическую ошибку и генерируем исключение
                logger.critical(f"Не удалось подключиться к базе данных после {retries} попыток.")
                # Генерируем исключение, чтобы остановить выполнение приложения
                raise ConnectionError(f"Не удалось подключиться к базе данных после {retries} попыток.") from e
        except Exception as e:
             # Логгируем любые другие неожиданные ошибки
             logger.error(f"Неожиданная ошибка при проверке подключения к БД: {e}", exc_info=True)
             if i < retries - 1:
                 logger.info(f"Повторная попытка через {delay} секунд...")
                 await asyncio.sleep(delay)
             else:
                 raise

    # Этот код не должен быть достигнут при успешном подключении или после исключения
    return False # На всякий случай