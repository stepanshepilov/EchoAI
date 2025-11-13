# Файл: test_ws_server.py

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def handler(websocket, path):
    """
    Обработчик для каждого нового подключения.
    """
    client_address = websocket.remote_address
    logging.info(f"Новый клиент подключился: {client_address}")
    
    try:
        # Бесконечно ждем сообщений от клиента (вашего бота)
        async for message in websocket:
            logging.info(f"<<< Получено сообщение от {client_address}: {message}")
            
            # Опционально: можно отправить ответ, чтобы проверить двустороннюю связь
            # await websocket.send(f"Сервер получил ваше сообщение: {message}")

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