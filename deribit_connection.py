import os
from dotenv import load_dotenv
import asyncio
import websockets
import json
import hmac
import hashlib
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

class WebSocketClient:
    def __init__(self, uri):
        self.uri = uri
        self.client = None
        self.lock = asyncio.Lock()

    async def connect(self):
        self.client = await websockets.connect(self.uri)

    async def receive(self):
        async with self.lock:
            return await self.client.recv()

    async def send(self, message):
        async with self.lock:
            await self.client.send(message)

class DeribitConnection:
    def __init__(self, client_id, client_secret, uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = WebSocketClient(uri)
        self.is_authenticated = False

    async def manage_connection(self):
        while True:
            try:
                if not self.client.websocket or self.client.websocket.closed:
                    await self.connect()
                    if not self.is_authenticated:
                        await self.authenticate()
                    await self.subscribe()
                response = await self.client.receive()
                self.process_response(response)
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection is closed, attempting to reconnect...")
                self.is_authenticated = False
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    async def connect(self):
        await self.client.connect()
        print("Successfully connected to WebSocket")

    async def authenticate(self):
        # Убедитесь, что вы используете self.client для отправки сообщений
        timestamp = int(datetime.now().timestamp() * 1000)
        nonce = str(int(datetime.now().timestamp() * 1000000))
        data = ''
        signature = hmac.new(
            bytes(self.client_secret, 'latin-1'),
            msg=bytes(f'{timestamp}\n{nonce}\n{data}', 'latin-1'),
            digestmod=hashlib.sha256
        ).hexdigest().lower()

        auth_msg = {
            "jsonrpc": "2.0",
            "id": 998,
            "method": "public/auth",
            "params": {
                "grant_type": "client_signature",
                "client_id": self.client_id,
                "timestamp": timestamp,
                "signature": signature,
                "nonce": nonce,
                "data": data
            }
        }

        await self.client.send(json.dumps(auth_msg))
        auth_response = json.loads(await self.client.receive())
        print(f"Authentication response: {auth_response}")
        if 'result' in auth_response:
            self.is_authenticated = True

    async def subscribe(self):
        subscribe_msg = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "id": 42,
            "params": {
                "channels": ["ticker.BTC-PERPETUAL.raw"]
            }
        }
        await self.client.send(json.dumps(subscribe_msg))
        subscribe_response = json.loads(await self.client.receive())
        print(f"Subscription response: {subscribe_response}")

    def process_response(self, response):
        # Обработка полученных данных
        try:
            parsed_response = json.loads(response)
            if 'method' in parsed_response:
                if parsed_response['method'] == 'subscription':
                    print(f"Received subscription data: {parsed_response['params']['data']}")
                # Добавьте обработку других методов
        except json.JSONDecodeError:
            print(f"Failed to parse JSON response: {response}")
