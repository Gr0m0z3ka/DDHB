from deribit_connection import DeribitConnection
from dotenv import load_dotenv
import os
import sys
import asyncio
import time
import websockets
import json
import hmac
import hashlib
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel,
                             QTextEdit, QComboBox, QGroupBox, QDoubleSpinBox, QSpinBox)
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QIcon, QColor, QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

# Загружаем переменные окружения из файла .env
load_dotenv()

# Логирование загруженных переменных окружения
client_id = os.getenv('api_key')
client_secret = os.getenv('api_secret')
print(f"Client ID: {client_id}")
print(f"Client Secret: {client_secret}")

class DeltaHedgerBot:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key

    def sign_request(self, request):
        timestamp = int(time.time() * 1000)
        signature_payload = f"{timestamp}{self.api_key}{json.dumps(request['method'])}{json.dumps(request['params']) if request['params'] else ''}"
        signature = hmac.new(self.secret_key.encode('utf-8'), signature_payload.encode('utf-8'), hashlib.sha256).hexdigest()

        request['params']['timestamp'] = timestamp
        request['params']['api_key'] = self.api_key
        request['params']['signature'] = signature
        
class BotInterface:
    def start_bot(self):
        asyncio.run_coroutine_threadsafe(self.deribit_connection.manage_connection(), asyncio.get_event_loop())
        
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#1e1e1e')  # Темный фон для графика
        self.axes = fig.add_subplot(111)
        self.axes.set_facecolor('#1e1e1e')  # Темный фон для области графика
        super(MplCanvas, self).__init__(fig)    

class BotInterface(QWidget):
    def __init__(self):
        self.client_id = os.getenv('API_KEY')
        self.client_secret = os.getenv('API_SECRET')
        super().__init__()
        self.bot = DeltaHedgerBot(client_id, client_secret)
        self.deribit_connection = DeribitConnection(self.client_id, self.client_secret, "wss://www.deribit.com/ws/api/v2")
        self.is_connected = False
        self.plot_data = {'time': [], 'delta': []}
        self.trades = []
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.current_delta = 0
        self.server_url = "wss://www.deribit.com/ws/api/v2"  # Реальный сервер Deribit
        self.connection_speed = 0  # Скорость подключения
        self.setStyleSheet("background-color: #1e1e1e; color: white;")  # Темный фон
        self.recv_semaphore = asyncio.Semaphore(1)  # Добавляем семафор для синхронизации доступа к recv
        self.initUI()

    def update_connection_status(self, color):
        self.connection_status.setStyleSheet(f"background-color: {color}; border-radius: 10px;")

    def initUI(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)  # Уменьшаем отступы

        # Левая часть интерфейса
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)  # Уменьшаем расстояние между элементами

        # Увеличиваем размер шрифта для всех элементов
        font = QFont("Arial", 10, QFont.Bold)

        self.currency_combo = QComboBox(self)
        self.currency_combo.addItems(["BTC", "ETH", "SOL"])
        self.currency_combo.setFont(font)
        left_layout.addWidget(QLabel("Currency"))
        left_layout.addWidget(self.currency_combo)

        self.long_combo = QComboBox(self)
        self.long_combo.addItems(["BTC-PERPETUAL", "ETH-PERPETUAL"])
        self.long_combo.setFont(font)
        left_layout.addWidget(QLabel("Long"))
        left_layout.addWidget(self.long_combo)

        self.short_combo = QComboBox(self)
        self.short_combo.addItems(["BTC-PERPETUAL", "ETH-PERPETUAL"])
        self.short_combo.setFont(font)
        left_layout.addWidget(QLabel("Short"))
        left_layout.addWidget(self.short_combo)

        self.order_type_combo = QComboBox(self)
        self.order_type_combo.addItems(["Taker", "Maker"])
        self.order_type_combo.setFont(font)
        left_layout.addWidget(QLabel("Order Type"))
        left_layout.addWidget(self.order_type_combo)

        self.split_order_threshold = QDoubleSpinBox(self)
        self.split_order_threshold.setRange(0, 1000)
        self.split_order_threshold.setSingleStep(0.1)
        self.split_order_threshold.setFont(font)
        left_layout.addWidget(QLabel("Split Order Threshold"))
        left_layout.addWidget(self.split_order_threshold)

        # Кнопки подключения и управления ботом
        self.connect_button = QPushButton('Connect')
        self.connect_button.setFixedSize(QSize(80, 30))  # Минимизируем размер кнопки
        self.connect_button.setStyleSheet("background-color: #0000FF; color: white;")
        self.connect_button.setFont(font)
        self.connect_button.clicked.connect(self.connect_to_exchange)
        left_layout.addWidget(self.connect_button)

        save_button = QPushButton('Save')
        save_button.setFixedSize(QSize(80, 30))
        save_button.setStyleSheet("background-color: #FFA500; color: black;")
        save_button.setFont(font)
        left_layout.addWidget(save_button)

        self.start_button = QPushButton('Run')
        self.start_button.setFixedSize(QSize(80, 30))
        self.start_button.setStyleSheet("background-color: #008000; color: white;")
        self.start_button.setFont(font)
        self.start_button.clicked.connect(self.start_bot)
        self.start_button.setEnabled(False)
        left_layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Stop')
        self.stop_button.setFixedSize(QSize(80, 30))
        self.stop_button.setStyleSheet("background-color: #FF0000; color: white;")
        self.stop_button.setFont(font)
        self.stop_button.clicked.connect(self.stop_bot)
        self.stop_button.setEnabled(False)
        left_layout.addWidget(self.stop_button)

        # Индикатор статуса подключения в виде лампочки
        self.connection_status = QLabel(self)
        self.connection_status.setFixedSize(20, 20)
        self.connection_status.setStyleSheet("background-color: red; border-radius: 10px;")
        left_layout.addWidget(self.connection_status, alignment=Qt.AlignCenter)

        # Скорость подключения
        self.connection_speed_label = QLabel(f"Speed: {self.connection_speed} ms", self)
        self.connection_speed_label.setFont(font)    
        left_layout.addWidget(self.connection_speed_label, alignment=Qt.AlignCenter)

        # Поле для отображения текущего сервера
        self.server_label = QLabel(f"Server: {self.server_url}")
        self.server_label.setFont(font)
        left_layout.addWidget(self.server_label)

        # Правая часть интерфейса
        right_layout = QVBoxLayout()

        # График
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        right_layout.addWidget(self.canvas)

        # Группы настроек
        long_group = QGroupBox("Long Position Setup")
        long_group.setStyleSheet("QGroupBox { border: 1px solid green; border-radius: 5px; margin-top: 0.5em; padding-top: 0.5em; }")
        long_layout = QVBoxLayout()
        long_layout.addWidget(QLabel("Negative Deviation Delta:"))
        self.long_negative_deviation = QLineEdit("0.0000")
        self.long_negative_deviation.setFont(font)
        long_layout.addWidget(self.long_negative_deviation)
        long_layout.addWidget(QLabel("Hedge Threshold"))
        self.long_hedge_threshold = QDoubleSpinBox(self)
        self.long_hedge_threshold.setRange(0, 1000)
        self.long_hedge_threshold.setSingleStep(0.1)
        self.long_hedge_threshold.setFont(font)
        long_layout.addWidget(self.long_hedge_threshold)
        long_layout.addWidget(QLabel("Hedge Ratio"))
        self.long_hedge_ratio = QSpinBox(self)
        self.long_hedge_ratio.setRange(0, 1000)
        self.long_hedge_ratio.setFont(font)
        long_layout.addWidget(self.long_hedge_ratio)
        long_group.setLayout(long_layout)

        target_group = QGroupBox("Target Delta")
        target_group.setStyleSheet("QGroupBox { border: 1px solid orange; border-radius: 5px; margin-top: 0.5em; padding-top: 0.5em; }")
        target_layout = QVBoxLayout()
        target_layout.addWidget(QLabel("Delta Total:"))
        self.target_delta_total = QLineEdit("0.0000")
        self.target_delta_total.setFont(font)
        target_layout.addWidget(self.target_delta_total)
        target_layout.addWidget(QLabel("Target Delta"))
        self.target_delta = QDoubleSpinBox(self)
        self.target_delta.setRange(-1000, 1000)
        self.target_delta.setSingleStep(0.1)
        self.target_delta.setFont(font)
        target_layout.addWidget(self.target_delta)
        target_group.setLayout(target_layout)

        short_group = QGroupBox("Short Position Setup")
        short_group.setStyleSheet("QGroupBox { border: 1px solid red; border-radius: 5px; margin-top: 0.5em; padding-top: 0.5em; }")
        short_layout = QVBoxLayout()
        short_layout.addWidget(QLabel("Positive Deviation Delta:"))
        self.short_positive_deviation = QLineEdit("0.0000")
        self.short_positive_deviation.setFont(font)
        short_layout.addWidget(self.short_positive_deviation)
        short_layout.addWidget(QLabel("Hedge Threshold"))
        self.short_hedge_threshold = QDoubleSpinBox(self)
        self.short_hedge_threshold.setRange(0, 1000)
        self.short_hedge_threshold.setSingleStep(0.1)
        self.short_hedge_threshold.setFont(font)
        short_layout.addWidget(self.short_hedge_threshold)
        short_layout.addWidget(QLabel("Hedge Ratio"))
        self.short_hedge_ratio = QSpinBox(self)
        self.short_hedge_ratio.setRange(0, 1000)
        self.short_hedge_ratio.setFont(font)
        short_layout.addWidget(self.short_hedge_ratio)
        short_group.setLayout(short_layout)

        # Информация о портфеле
        portfolio_group = QGroupBox("Portfolio Info")
        portfolio_group.setStyleSheet("QGroupBox { border: 1px solid cyan; border-radius: 5px; margin-top: 0.5em; padding-top: 0.5em; }")
        portfolio_layout = QVBoxLayout()

        self.portfolio_combo = QComboBox(self)
        self.portfolio_combo.addItems(["BTC", "ETH", "SOL"])
        self.portfolio_combo.setFont(font)
        self.portfolio_combo.currentTextChanged.connect(self.update_portfolio_info)
        portfolio_layout.addWidget(self.portfolio_combo)

        self.portfolio_info = QTextEdit(self)
        self.portfolio_info.setReadOnly(True)
        self.portfolio_info.setFont(font)
        portfolio_layout.addWidget(self.portfolio_info)

        portfolio_group.setLayout(portfolio_layout)
        right_layout.addWidget(portfolio_group)

        # Греки
        greeks_group = QGroupBox("Greeks")
        greeks_group.setStyleSheet("QGroupBox { border: 1px solid magenta; border-radius: 5px; margin-top: 0.5em; padding-top: 0.5em; }")
        greeks_layout = QVBoxLayout()
        self.delta_label = QLabel("Delta: 0")
        self.gamma_label = QLabel("Gamma: 0")
        self.vega_label = QLabel("Vega: 0")
        self.theta_label = QLabel("Theta: 0")
        for label in [self.delta_label, self.gamma_label, self.vega_label, self.theta_label]:
            label.setFont(font)
            greeks_layout.addWidget(label)
        greeks_group.setLayout(greeks_layout)
        right_layout.addWidget(greeks_group)

        # Общий баланс       
        self.balance_label = QLabel("Total Balance: $0")
        self.balance_label.setFont(font)
        right_layout.addWidget(self.balance_label)

        # Выбор стратегии
        strategy_group = QGroupBox("Strategy")
        strategy_group.setStyleSheet("QGroupBox { border: 1px solid yellow; border-radius: 5px; margin-top: 0.5em; padding-top: 0.5em; }")
        strategy_layout = QVBoxLayout()
        self.strategy_combo = QComboBox(self)
        self.strategy_combo.addItems(["Strategy 1", "Strategy 2", "Strategy 3"])  # Заглушки для стратегий
        self.strategy_combo.setFont(font)
        strategy_layout.addWidget(self.strategy_combo)
        strategy_group.setLayout(strategy_layout)
        right_layout.addWidget(strategy_group)

        right_layout.addStretch(1)  # Добавляем пространство внизу, чтобы элементы не прилипали к нижнему краю

        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

        self.setWindowTitle('Delta Hedger Bot')
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.data_update_timer = QTimer(self)
        self.data_update_timer.timeout.connect(lambda: asyncio.run_coroutine_threadsafe(self._update_data_from_exchange(), self.loop))
        self.data_update_timer.start(1000)  # Обновляем данные каждую секунду

    def connect_to_exchange(self):
        if not self.is_connected:
            try:
                self.loop.run_until_complete(self.connect_to_websocket())
                self.is_connected = True
                self.connection_status.setStyleSheet("background-color: green; border-radius: 10px;")
                self.connect_button.setText("Disconnect")
                self.start_button.setEnabled(True)
                self.data_update_timer.start(1000)  # Начинаем обновление данных
                print("Successfully connected to WebSocket")
            except Exception as e:
                print(f"Connection failed: {e}")
                self.connection_status.setStyleSheet("background-color: red; border-radius: 10px;")
        else:
            self.is_connected = False
            self.connection_status.setStyleSheet("background-color: red; border-radius: 10px;")
            self.connect_button.setText("Connect")
            self.start_button.setEnabled(False)
            self.stop_bot()
            self.data_update_timer.stop()  # Останавливаем обновление данных
            print("Disconnected from WebSocket")

    async def connect_to_websocket(self):
        try:
            await self.deribit_connection.connect()
            self.is_connected = True
            self.loop.call_soon_threadsafe(self.update_connection_status, "green")
        except Exception as e:
            print(f"Ошибка подключения к WebSocket: {e}")
            self.loop.call_soon_threadsafe(self.update_connection_status, "red")

    def update_portfolio_info(self, currency):
        if self.is_connected:
            asyncio.run_coroutine_threadsafe(self._update_portfolio_info(currency), self.loop)

    async def _update_portfolio_info(self, currency):
        if self.deribit_connection.websocket:
            # Запрос информации о портфеле для выбранной валюты
            portfolio_request = {
                "method": "private/get_portfolio",
                "params": {
                    "currency": currency
                },
                "jsonrpc": "2.0",
                "id": 1000
            }
            signed_portfolio_request = self.bot.sign_request(portfolio_request)
            await self.deribit_connection.websocket.send(json.dumps(signed_portfolio_request))
            response = await self.deribit_connection.websocket.recv()
            portfolio_data = json.loads(response)
            if 'result' in portfolio_data:
                portfolio_info = portfolio_data['result']
                # Формируем текст для отображения информации о портфеле
                info_text = f"Portfolio Info for {currency}:\n\n"
                for item in portfolio_info:
                    info_text += f"Futures: {item.get('futures', 0)}\n"
                    info_text += f"Options: {item.get('options', 0)}\n"
                    info_text += f"Spot: {item.get('spot', 0)}\n\n"
                self.portfolio_info.setText(info_text)
            else:
                self.portfolio_info.setText("Error fetching portfolio data")

    async def _update_data_from_exchange(self):
        while True:
            try:
                if self.deribit_connection.websocket is not None:
                    async with self.recv_semaphore:  # Используем семафор для синхронизации
                        try:
                            await self.deribit_connection.websocket.ping()
                        except websockets.exceptions.ConnectionClosed:
                            print("WebSocket connection is closed, attempting to reconnect...")
                            await self.connect_to_websocket()
                            continue

                        # Отправка пинга для поддержания соединения
                        ping_request = {
                            "jsonrpc": "2.0",
                            "id": 9098,
                            "method": "public/ping",
                            "params": {}
                        }
                        await self.deribit_connection.websocket.send(json.dumps(ping_request))
                        pong_response = await self.deribit_connection.websocket.recv()
                        pong_data = json.loads(pong_response)
                        print("Received pong:", pong_data)

                        # Запрос на получение греков портфеля
                        greeks_request = {
                            "jsonrpc": "2.0",
                            "id": 1234,
                            "method": "private/get_portfolio_greeks",
                            "params": {}
                        }
                        signed_greeks_request = self.bot.sign_request(greeks_request)
                        await self.deribit_connection.websocket.send(json.dumps(signed_greeks_request))
                        response = await self.deribit_connection.websocket.recv()
                        response_data = json.loads(response)
                        if 'result' in response_data:
                            greeks = response_data['result']
                            self.delta_label.setText(f"Delta: {greeks.get('delta', 0):.2f}")
                            self.gamma_label.setText(f"Gamma: {greeks.get('gamma', 0):.2f}")
                            self.vega_label.setText(f"Vega: {greeks.get('vega', 0):.2f}")
                            self.theta_label.setText(f"Theta: {greeks.get('theta', 0):.2f}")
                            print("Получены данные о греках:", greeks)
                        else:
                            print("Ошибка при получении данных о греках:", response_data.get('error', {}))

                        # Задержка перед следующим запросом греков
                        await asyncio.sleep(1)  # 1 секунда задержки, чтобы не превышать лимиты

                        # Запрос на получение баланса
                        balance_request = {
                            "jsonrpc": "2.0",
                            "id": 5678,
                            "method": "private/get_account_summary",
                            "params": {}
                        }
                        signed_balance_request = self.bot.sign_request(balance_request)
                        await self.deribit_connection.websocket.send(json.dumps(signed_balance_request))
                        response = await self.deribit_connection.websocket.recv()
                        response_data = json.loads(response)
                        if 'result' in response_data:
                            balance = response_data['result']
                            total_balance = balance.get('equity', 0)
                            self.balance_label.setText(f"Total Balance: ${total_balance:.2f}")
                            print("Получен баланс:", balance)
                        else:
                            print("Ошибка при получении баланса:", response_data.get('error', {}))

                        # Задержка перед следующим циклом запросов
                        await asyncio.sleep(59)  # Оставляем 1 секунду для запроса греков в следующем цикле, чтобы не превышать 60 секунд
                else:
                    print("WebSocket is not connected, attempting to connect...")
                    await self.connect_to_websocket()
            except websockets.exceptions.ConnectionClosedOK:
                print("Connection closed, reconnecting...")
                await asyncio.sleep(5)
                await self.connect_to_websocket()
            except Exception as e:
                print(f"Ошибка при получении данных: {e}")
                await asyncio.sleep(5)
                await self.connect_to_websocket()

    def sign_request(self, request):
        return self.bot.sign_request(request)

    def start_bot(self):
        if self.is_connected:
            symbol = self.long_combo.currentText()
            delta_threshold = self.target_delta.value()
            client_id = os.getenv('api_key')
            client_secret = os.getenv('api_secret')
            if client_id and client_secret:
                self.stop_button.setEnabled(True)
                self.start_button.setEnabled(False)
                print("Starting bot...")
                self.bot_task = asyncio.create_task(self.run_bot())
                print("Bot started")

    async def run_bot(self):
        try:
            while True:
                # Здесь должна быть логика работы бота
                await asyncio.sleep(1)  # Задержка для предотвращения чрезмерной нагрузки на CPU
        except asyncio.CancelledError:
            print("Bot task was cancelled.")
        except Exception as e:
            print(f"Bot encountered an error: {e}")

    def stop_bot(self):
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)
        if hasattr(self, 'bot_task') and self.bot_task:
            self.bot_task.cancel()
            print("Bot stopped.")
            try:
                self.loop.run_until_complete(asyncio.sleep(0))  # Даем время для отмены задачи
            except Exception as e:
                print(f"Error while stopping bot: {e}")

    def update_delta_data(self, new_delta):
        # Этот метод вызывается из delta_hedger_bot для обновления данных дельты
        self.current_delta = new_delta
        self.plot_data['time'].append(time.time())
        self.plot_data['delta'].append(new_delta)
        if len(self.plot_data['time']) > 100:
            self.plot_data['time'].pop(0)
            self.plot_data['delta'].pop(0)

    def update_plot(self):
        self.canvas.axes.clear()
        self.canvas.axes.plot(self.plot_data['time'], self.plot_data['delta'], color='gray')  # Линия серого цвета
        self.canvas.axes.set_xlabel('Time')
        self.canvas.axes.set_ylabel('Delta')
        self.canvas.axes.set_title('Delta Over Time')
        self.canvas.axes.tick_params(colors='white')  # Цвет меток осей
        self.canvas.axes.spines['bottom'].set_color('white')
        self.canvas.axes.spines['top'].set_color('white')
        self.canvas.axes.spines['right'].set_color('white')
        self.canvas.axes.spines['left'].set_color('white')
        self.canvas.draw()

    def custom_exec(self):
        return QApplication.instance().exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = BotInterface()
    try:
        timer = QTimer()
        timer.timeout.connect(lambda: ex.loop.run_until_complete(asyncio.sleep(0)))
        timer.start(100)

        ex.timer.start(1000)
        ex.show()
        sys.exit(ex.custom_exec())
    except Exception as e:
        print(f"An error occurred: {e}")
    
    
