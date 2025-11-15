import asyncio
import websockets
import json


async def listen():
    """
    Подключается к WebSocket серверу и слушает входящие сообщения.
    """
    uri = "ws://127.0.0.1:8000/api/v1/ws/dashboard"

    # Используем бесконечный цикл для автоматического переподключения
    while True:
        try:
            # Устанавливаем соединение
            async with websockets.connect(uri) as websocket:
                print(f"Успешно подключился к {uri}")
                # Бесконечно ждем сообщений от сервера
                async for message in websocket:
                    try:
                        # Преобразуем JSON-строку в Python-словарь для красивого вывода
                        data = json.loads(message)
                        print("<<< ПОЛУЧЕНО СООБЩЕНИЕ:")
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                    except json.JSONDecodeError:
                        print(f"<<< Получена не-JSON строка: {message}")

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError):
            print("Соединение потеряно. Попытка переподключения через 5 секунд...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Произошла ошибка: {e}. Попытка переподключения через 5 секунд...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    print("Запуск WebSocket клиента-слушателя. Нажмите CTRL+C для выхода.")
    asyncio.run(listen())