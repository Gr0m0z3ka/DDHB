import asyncio
import websockets
import json
import hmac
import hashlib
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

async def authenticate(websocket, client_id, client_secret):
    timestamp = int(datetime.now().timestamp() * 1000)
    signature = hmac.new(
        bytes(client_secret, "utf-8"),
        msg=bytes(f"{timestamp}\nYOUR_NONCE", "utf-8"),  # Замените YOUR_NONCE на реальный nonce
        digestmod=hashlib.sha256
    ).hexdigest()
    
    auth_msg = {
        "method": "public/auth",
        "params": {
            "grant_type": "client_signature",
            "client_id": client_id,
            "timestamp": timestamp,
            "signature": signature
        }
    }
    await websocket.send(json.dumps(auth_msg))
    auth_response = await websocket.recv()
    print(f"Auth Response: {auth_response}")

async def subscribe_positions(websocket):
    subscribe_msg = {
        "method": "private/subscribe",
        "params": {
            "channels": ["user.positions"]
        }
    }
    await websocket.send(json.dumps(subscribe_msg))

async def place_order(websocket, method, symbol, amount, order_type="market"):
    order_msg = {
        "method": method,  # 'private/buy' или 'private/sell'
        "params": {
            "instrument_name": symbol,
            "amount": amount,
            "type": order_type  # или 'limit' для лимитных ордеров
        }
    }
    await websocket.send(json.dumps(order_msg))
    order_response = await websocket.recv()
    response_data = json.loads(order_response)
    print(f"Order Response: {response_data}")
    return response_data

async def delta_hedger(symbol, delta_threshold, client_id, client_secret, update_delta_callback):
    uri = "wss://test.deribit.com/ws/api/v2"  # Используйте тестовый сервер для отладки
    async with websockets.connect(uri) as websocket:
        await authenticate(websocket, client_id, client_secret)
        await subscribe_positions(websocket)

        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)
                if 'method' in data and data['method'] == 'subscription':
                    for position in data['params']['data']:
                        if position['instrument_name'] == symbol:
                            current_delta = position.get('delta', 0)  # Предполагаем, что 'delta' есть в данных
                            update_delta_callback(current_delta)  # Обновляем данные для графика
                            if abs(current_delta) >= delta_threshold:
                                print(f"Delta changed by {delta_threshold} for {symbol}")
                                method = "private/buy" if current_delta > 0 else "private/sell"
                                # Отправка ордера
                                order_response = await place_order(websocket, method, symbol, "1")  # Здесь "1" - это количество контрактов, измените по необходимости
                                if order_response.get('success'):
                                    print(f"Successfully placed order: {order_response}")
                                else:
                                    print(f"Failed to place order: {order_response}")
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed, attempting to reconnect...")
                await asyncio.sleep(5)  # Подождите 5 секунд перед попыткой переподключения
                return await delta_hedger(symbol, delta_threshold, client_id, client_secret, update_delta_callback)
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    client_id = os.getenv('DERIBIT_CLIENT_ID')
    client_secret = os.getenv('DERIBIT_CLIENT_SECRET')
    symbol = "BTC-PERPETUAL"  # Пример инструмента
    delta_threshold = 1  # Изменение дельты на 1
    
    async def main():
        await delta_hedger(symbol, delta_threshold, client_id, client_secret, lambda x: print(f"Delta updated: {x}"))
    
    import asyncio
    asyncio.run(main())