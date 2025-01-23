# deribit_connection.py

import asyncio
import websockets
import json
import hmac
import hashlib
from dotenv import load_dotenv
import os
import time

# Загрузка переменных окружения
load_dotenv()

class DeribitConnection:
    def __init__(self, api_key, api_secret, websocket_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.websocket_url = websocket_url
        self.websocket = None
        self.access_token = None

    async def connect(self):
        """Подключение к WebSocket и аутентификация"""
        try:
            # Подключаемся к WebSocket
            self.websocket = await websockets.connect(self.websocket_url)
            if self.websocket is not None:
                print("Успешно подключено к WebSocket")
                await self.authenticate()
                await self.subscribe_to_channels()
            else:
                raise Exception("Failed to establish WebSocket connection")
        except Exception as e:
            print(f"Ошибка подключения к WebSocket: {e}")
            if self.websocket:
                await self.websocket.close()
            self.websocket = None
            raise

    async def authenticate(self):
        """Аутентификация на сервере Deribit"""
        auth_message = {
            "jsonrpc": "2.0",
            "id": 998,
            "method": "public/auth",
            "params": {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret
            }
        }
        print(f"Sending auth message: {auth_message}")  # Лог запроса
        await self.websocket.send(json.dumps(auth_message))

        response = await self.websocket.recv()
        auth_result = json.loads(response)
        print(f"Authentication response: {auth_result}")  # Лог ответа

        if 'error' in auth_result:
            raise Exception(f"Authentication failed: {auth_result['error']['message']}")
        self.access_token = auth_result['result']['access_token']

    async def subscribe_to_channels(self):
        """Подписка на каналы"""
        subscribe_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "private/subscribe",
            "params": {
                "channels": ["user.portfolio", "user.greeks"]
            }
        }
        await self.websocket.send(json.dumps(subscribe_message))
        response = await self.websocket.recv()
        subscribe_result = json.loads(response)
        print(f"Subscription response: {subscribe_result}")

        if 'error' in subscribe_result:
            raise Exception(f"Subscription failed: {subscribe_result['error']['message']}")

    def sign_request(self, request):
        """Подпись запроса"""
        timestamp = int(time.time() * 1000)
        signature_payload = f"{timestamp}{self.api_key}{json.dumps(request['method'])}{json.dumps(request['params']) if request['params'] else ''}"
        signature = hmac.new(self.api_secret.encode('utf-8'), signature_payload.encode('utf-8'), hashlib.sha256).hexdigest()

        request['params']['timestamp'] = timestamp
        request['params']['api_key'] = self.api_key
        request['params']['signature'] = signature

        return request

    async def close_connection(self):
        """Закрытие соединения"""
        if self.websocket:
            await self.websocket.close()
            print("WebSocket connection closed")
            self.websocket = None