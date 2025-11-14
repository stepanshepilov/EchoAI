import asyncio
import websockets

async def test_ws():
    uri = "ws://127.0.0.1:8000/api/v1/ws/dashboard"
    async with websockets.connect(uri) as websocket:
        print("WebSocket соединение установлено!")
        try:
            while True:
                msg = await websocket.recv()
                print("Получено сообщение:", msg)
        except websockets.ConnectionClosed:
            print("Соединение закрыто")

asyncio.run(test_ws())