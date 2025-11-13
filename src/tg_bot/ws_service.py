# Файл: src/services/ws_notifier.py
import asyncio
import websockets
import logging
import json

logger = logging.getLogger(__name__)

WEBSOCKET_URI = "ws://127.0.0.1:8000/api/v1/ws/dashboard"

class WebSocketNotifier:
    def __init__(self, uri: str):
        self.uri = uri
        self._connection = None
        self._is_running = False
        self._connection_task = None
        # Убираем Event из __init__

    async def _connect_loop(self, startup_event: asyncio.Event):
        """
        Бесконечный цикл для поддержания соединения.
        Принимает 'startup_event' для уведомления о первом подключении.
        """
        self._is_running = True
        is_first_connection = True
        
        while self._is_running:
            try:
                logger.info(f"Попытка подключения к WebSocket: {self.uri}")
                async with websockets.connect(self.uri) as websocket:
                    self._connection = websocket
                    logger.info("WebSocket соединение установлено!")
                    
                    # ### ИСПРАВЛЕНО: Уведомляем о первом подключении ###
                    if is_first_connection:
                        startup_event.set()
                        is_first_connection = False
                    
                    await websocket.wait_closed()

            except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
                logger.warning(f"WebSocket соединение потеряно или не удалось: {e}. Повторная попытка через 5с...")
            except Exception as e:
                logger.error(f"Непредвиденная ошибка в WebSocket цикле: {e}", exc_info=True)
            finally:
                self._connection = None
                if self._is_running:
                    await asyncio.sleep(5)

    async def start(self):
        """
        Запускает фоновую задачу и ЖДЕТ первого успешного подключения.
        """
        if self._is_running:
            return
            
        logger.info("Запуск сервиса WebSocket уведомлений...")
        
        # ### ИСПРАВЛЕНО: Создаем Event здесь и передаем его в задачу ###
        startup_event = asyncio.Event()
        
        self._connection_task = asyncio.create_task(self._connect_loop(startup_event))
        
        try:
            # Ждем, пока _connect_loop не поднимет переданный ему флажок
            await asyncio.wait_for(startup_event.wait(), timeout=10.0)
            logger.info("Сервис WebSocket уведомлений запущен и успешно подключен.")
        except asyncio.TimeoutError:
            logger.error("!!! Не удалось подключиться к WebSocket за 10 секунд. Бот запускается без WS-уведомлений.")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при запуске WS сервиса: {e}", exc_info=True)

            
    async def stop(self):
        """Останавливает сервис и закрывает соединение."""
        self._is_running = False
        if self._connection:
            await self._connection.close()
        if self._connection_task:
            self._connection_task.cancel()
        logger.info("Сервис WebSocket уведомлений остановлен.")

    async def send(self, data: dict):
        """
        Отправляет данные на сервер, если соединение установлено.
        """
        if self._connection and self._connection.open:
            try:
                # Конвертируем словарь в JSON-строку перед отправкой
                await self._connection.send(json.dumps(data))
                logger.info(f"Отправлено WebSocket сообщение: {data}")
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Попытка отправки в закрытое WebSocket соединение.")
        else:
            logger.warning("WebSocket соединение не установлено. Сообщение не отправлено.")

ws_notifier = WebSocketNotifier(WEBSOCKET_URI)


