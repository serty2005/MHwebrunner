import asyncio

from data_validator import clearify_server_data  # Импортируем функцию из нашего модуля

# Примеры тестовых данных
test_data_list = [
    {
        "UUID": "123e4567-e89b-12d3-a456-426614174000",
        "IP": "https://mycompany.iiko.it/server",
        "CabinetLink": "https://partners.iiko.ru/ru/cabinet/clients.html?mode=showOne&id=12345",
        "UniqueID": "123-456-789",
        "Teamviewer": "Пароль от учётки Windows 27042018 \n MH_10552",
        "AnyDesk": "987654321",
        "RDP": "RDP1234567890"
    },
    {
        "UUID": "789e1234-a89b-23c3-b456-426614170999",
        "IP": "192.168.0.1:8080",
        "CabinetLink": "https://partners.iiko.ru/en/cabinet/clients.html?mode=showOne&id=98765",
        "UniqueID": None,
        "Teamviewer": "TV ID 1122334455",
        "AnyDesk": "302273084 Zz89852228558",
        "RDP": ""
    }
]

# Асинхронная функция для тестирования
async def test_clearify_server_data():
    for idx, test_data in enumerate(test_data_list):
        print(f"==== Тест №{idx + 1} ====")
        validated_data = await clearify_server_data(test_data)
        print("Результат валидации:", validated_data)
        print("=====================\n")

# Запуск тестов
if __name__ == "__main__":
    asyncio.run(test_clearify_server_data())
