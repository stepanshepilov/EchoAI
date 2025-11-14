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
            try:
                data = json.loads(message_str)
                logging.info(f"<<< Получено сообщение от {client_address}: {data}")
                
            except json.JSONDecodeError:
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
    
    async with websockets.serve(handler, host, port):
        logging.info(f"Тестовый WebSocket сервер запущен на ws://{host}:{port}")
        logging.info("Ожидание подключений от бота...")
        logging.info("Нажмите Ctrl+C для остановки.")
        
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Сервер остановлен.")