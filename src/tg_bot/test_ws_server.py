# Файл: test_ws_server.py

import asyncio
import websockets
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def handler(websocket, path):
    """
    Обработчик для каждого нового подключения.
    """
    client_address = websocket.remote_address
    logging.info(f"Новый клиент подключился: {client_address}")
    
    try:
        async for message_str in websocket:
            # ### ИЗМЕНЕНИЯ ЗДЕСЬ ###
            try:
                # 2. Пытаемся превратить строку в объект Python (словарь)
                data = json.loads(message_str)
                # 3. Печатаем уже красивый, "расшифрованный" объект
                logging.info(f"<<< Получено сообщение от {client_address}: {data}")
                
            except json.JSONDecodeError:
                # Если пришла невалидная JSON-строка
                logging.warning(f"Получена невалидная JSON-строка: {message_str}")

    except websockets.exceptions.ConnectionClosed as e:
        logging.warning(f"Клиент {client_address} отключился: {e}")
    except Exception as e:
        logging.error(f"Произошла ошибка с клиентом {client_address}: {e}", exc_info=True)

async def main():
    """
    Основная функция для запуска сервера.
    """
    host = "127.0.0.1"
    port = 8000
    
    # Запускаем WebSocket сервер
    async with websockets.serve(handler, host, port):
        logging.info(f"Тестовый WebSocket сервер запущен на ws://{host}:{port}")
        logging.info("Ожидание подключений от бота...")
        logging.info("Нажмите Ctrl+C для остановки.")
        
        # Сервер будет работать вечно, пока его не прервут
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Сервер остановлен.")