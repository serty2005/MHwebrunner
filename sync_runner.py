import asyncio
import logging
from datetime import datetime
from models import SessionLocal
from services import ServiceDeskService
import os
from dotenv import load_dotenv
import random
import httpx

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'sync_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("SyncRunner")

# Загрузка переменных окружения
load_dotenv()

async def run_sync():
    """Запуск синхронизации данных"""
    session = SessionLocal()
    try:
        service = ServiceDeskService(session)
        
        # Начало синхронизации
        start_time = datetime.now()
        logger.info("Начало синхронизации данных")
        
        # Запуск синхронизации
        await service.sync_all_data()
        
        # Завершение синхронизации
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"Синхронизация завершена. Длительность: {duration}")
        
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}")
        raise
    finally:
        session.close()

async def test_sync():
    """Тестирование синхронизации с выборочной компанией"""
    session = SessionLocal()
    try:
        service = ServiceDeskService(session)
        
        # Получение списка компаний
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            companies = await service.fetch_companies()
            
            # Выбор тестовой компании из середины списка
            if companies:
                total_companies = len(companies)
                logger.info(f"Всего получено компаний: {total_companies}")
                
                # Выбираем случайный индекс от 10 до min(700, total_companies - 1)
                if total_companies <= 10:
                    logger.warning("Слишком мало компаний для тестирования из середины списка")
                    return
                    
                max_index = min(700, total_companies - 1)
                test_index = random.randint(10, max_index)
                test_company = companies[test_index]
                
                logger.info(f"Выбрана компания #{test_index} из {total_companies}: {test_company.get('title')}")
                
                # Синхронизация тестовой компании
                company = await service.sync_company(client, test_company)
                if company:
                    logger.info(f"Компания успешно синхронизирована: {company.title}")
                    
                    # Проверка оборудования
                    equipment_count = {
                        'servers': 0,
                        'workstations': 0,
                        'fr': 0
                    }
                    
                    for equipment in test_company.get('KEsInUse', []):
                        if equipment['metaClass'] == 'objectBase$Server':
                            await service.sync_server(equipment, company.uuid)
                            equipment_count['servers'] += 1
                        elif equipment['metaClass'] == 'objectBase$Workstation':
                            await service.sync_workstation(equipment, company.uuid)
                            equipment_count['workstations'] += 1
                        elif equipment['metaClass'] == 'objectBase$FR':
                            equipment_count['fr'] += 1
                    
                    logger.info(f"Статистика оборудования для компании {company.title}:")
                    logger.info(f"Серверов: {equipment_count['servers']}")
                    logger.info(f"Рабочих станций: {equipment_count['workstations']}")
                    logger.info(f"ФР (пропущено): {equipment_count['fr']}")
            else:
                logger.warning("Компании не найдены")
                
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Запуск тестовой синхронизации
        asyncio.run(test_sync())
    else:
        # Запуск полной синхронизации
        asyncio.run(run_sync())
