# server_admin.py
import socket
import threading
import os
import json
import hashlib
import time
from typing import Dict, List

class DriverDeploymentServer:
    def __init__(self, host=None, port=8888):
        # Читаем конфиг и устанавливаем параметры
        config = self.load_config()
        self.host = host or config.get('server_host', '172.20.10.4')
        self.port = port or config.get('server_port', 8888)
        self.connected_clients: Dict[str, Dict] = {}
        self.clients_lock = threading.Lock()
        self.drivers_dir = "drivers"
        self.create_drivers_directory()
        
    def load_config(self):
        """Загружает конфигурацию из файла config.json"""
        config_path = "config.json"
        default_config = {
            "server_host": "172.20.10.4",
            "server_port": 8888
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"✅ Конфигурация сервера загружена из {config_path}")
                return config
            else:
                # Создаем файл с конфигурацией по умолчанию
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                print(f"📁 Создан файл конфигурации {config_path}")
                return default_config
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации сервера: {e}")
            return default_config
    
    def create_drivers_directory(self):
        """Создает централизованное хранилище драйверов"""
        if not os.path.exists(self.drivers_dir):
            os.makedirs(self.drivers_dir)
            
    def get_driver_list(self):
        """Возвращает список драйверов"""
        drivers = []
        for file in os.listdir(self.drivers_dir):
            file_path = os.path.join(self.drivers_dir, file)
            if os.path.isfile(file_path):
                drivers.append({
                    'name': file,
                    'size': os.path.getsize(file_path)
                })
        return drivers
    
    def safe_json_decode(self, data):
        """Безопасно декодирует JSON данные"""
        try:
            if isinstance(data, bytes):
                text = data.decode('utf-8').strip()
            else:
                text = str(data).strip()
            
            if not text:
                return None
            
            # Проверяем валидность JSON
            if not text.startswith('{') or not text.endswith('}'):
                return None
                
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка JSON декодирования: {e}")
            return None
        except Exception as e:
            print(f"❌ Ошибка декодирования: {e}")
            return None
    
    def get_system_info(self, client_socket) -> Dict:
        """Получает информацию о системе клиента"""
        try:
            command = {"action": "get_system_info"}
            client_socket.send(json.dumps(command).encode())
            
            client_socket.settimeout(5.0)
            response = client_socket.recv(4096).decode()
            return json.loads(response).get('system_info', {})
        except Exception as e:
            print(f"Ошибка получения системной информации: {e}")
            return {"os": "unknown", "architecture": "unknown"}
    
    def calculate_file_hash(self, file_path):
        """Вычисляет хеш файла"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def send_file(self, client_socket, file_path):
        """Отправляет файл клиенту"""
        try:
            file_size = os.path.getsize(file_path)
            file_info = {
                'name': os.path.basename(file_path),
                'size': file_size,
                'hash': self.calculate_file_hash(file_path)
            }
            
            # Отправляем информацию о файле
            file_info_json = json.dumps(file_info)
            client_socket.send(file_info_json.encode())
            
            # Ждем подтверждения
            client_socket.settimeout(5.0)
            ack = client_socket.recv(1024)
            if ack != b'ACK':
                print("Клиент не подтвердил получение информации о файле")
                return False
            
            # Отправляем файл
            with open(file_path, 'rb') as f:
                total_sent = 0
                while total_sent < file_size:
                    chunk = f.read(8192)  # Увеличиваем размер чанка
                    if not chunk:
                        break
                    sent = client_socket.send(chunk)
                    if sent == 0:
                        print("Соединение разорвано при отправке файла")
                        return False
                    total_sent += sent
                    
            print(f"✅ Файл {file_path} отправлен успешно")
            return True
            
        except socket.timeout:
            print(f"⏰ Таймаут при отправке файла")
            return False
        except Exception as e:
            print(f"❌ Ошибка отправки файла: {e}")
            return False
    
    def is_driver_compatible(self, driver_name: str, system_info: Dict) -> bool:
        """Проверяет совместимость драйвера с системой"""
        os_name = system_info.get('os', '').lower()
        
        if 'windows' in os_name and 'win' in driver_name.lower():
            return True
        elif 'linux' in os_name and 'linux' in driver_name.lower():
            return True
        elif 'network' in driver_name.lower():
            return True
            
        return False
    
    def deploy_to_client(self, pSocket, pDriverName):
        driver_selected = None
        if pSocket is None:
            return {"status": "error", "message": "Сокет клиента не найден или не подключён"}
        
        try:
            drivers = self.get_driver_list()
       
            for driver in drivers:
                cmp_driver = f"{driver['name']} {driver['size']} байт"
                if cmp_driver == pDriverName:
                    driver_selected = driver['name']
                    break

            if not driver_selected:
                return {"status": "error", "message": "Драйвер не найден"}

            command = {
                "action": "install_driver",
                "driver_name": driver_selected
            }

            print(f"🔄 Отправка команды установки драйвера: {driver_selected}")
            pSocket.send(json.dumps(command).encode())

            driver_path = os.path.join(self.drivers_dir, driver_selected)
            
            if self.send_file(pSocket, driver_path):
                print(f"✅ Файл отправлен, ожидаю результат установки...")
                
                pSocket.settimeout(180.0)  # 3 минуты на установку
                
                try:
                    response = pSocket.recv(8192).decode()  # Увеличиваем буфер
                    result = self.safe_json_decode(response)
                    if result:
                        print(f"📨 Получен результат от клиента: {result.get('status', 'unknown')}")
                        return result
                    else:
                        print(f"❌ Неверный формат ответа от клиента")
                        return {"status": "error", "message": "Неверный формат ответа от клиента"}
                    
                except socket.timeout:
                    print(f"⏰ Таймаут при ожидании результата установки")
                    return {"status": "error", "message": "Таймаут при ожидании результата установки"}
                except ConnectionResetError:
                    print(f"🔒 Соединение с клиентом разорвано во время установки")
                    return {"status": "error", "message": "Соединение разорвано во время установки"}
                    
            else:
                return {"status": "error", "message": "Ошибка отправки файла"}

        except socket.timeout:
            return {"status": "error", "message": "Таймаут при установке драйвера"}
        except ConnectionResetError:
            print(f"🔒 Соединение с клиентом разорвано")
            return {"status": "error", "message": "Соединение с клиентом разорвано"}
        except Exception as e:
            print(f"❌ Ошибка в deploy_to_client: {e}")
            return {"status": "error", "message": str(e)}
    
    def mass_deploy(self, driver_name: str):
        """Массовое развертывание драйвера на всех подключенных клиентах"""
        results = {}
        
        with self.clients_lock:
            client_ids = list(self.connected_clients.keys())
        
        for client_id in client_ids:
            try:
                with self.clients_lock:
                    if client_id not in self.connected_clients:
                        results[client_id] = {"status": "error", "message": "Клиент отключен"}
                        continue
                    
                    client_info = self.connected_clients[client_id]
                    client_socket = client_info['socket']
                
                system_info = self.get_system_info(client_socket)
                
                if self.is_driver_compatible(driver_name, system_info):
                    result = self.deploy_to_client(client_socket, driver_name)
                    results[client_id] = result
                else:
                    results[client_id] = {"status": "skipped", "message": "Несовместимый драйвер"}
                    
            except Exception as e:
                results[client_id] = {"status": "error", "message": str(e)}
                
        return results

    def handle_client(self, client_socket, address, client_id):
        """Обрабатывает подключение клиента"""
        print(f"🔗 Клиент {client_id} подключен: {address}")
        
        with self.clients_lock:
            self.connected_clients[client_id] = {
                'socket': client_socket,
                'address': address,
                'connected_at': time.time(),
                'last_activity': time.time()
            }
        
        try:
            while True:
                client_socket.settimeout(10.0)
                
                try:
                    data = client_socket.recv(8192).decode()  # Увеличиваем буфер
                    if not data:
                        print(f"🔒 Клиент {client_id} отключился")
                        break
                        
                    message = self.safe_json_decode(data)
                    if not message:
                        # Пропускаем не-JSON данные (скорее всего файловые)
                        continue
                    
                    print(f"📨 От клиента {client_id}: {message.get('action', 'unknown')}")
                    
                    with self.clients_lock:
                        if client_id in self.connected_clients:
                            self.connected_clients[client_id]['last_activity'] = time.time()
                    
                    if message['action'] == 'register_client':
                        with self.clients_lock:
                            self.connected_clients[client_id]['system_info'] = message['system_info']
                        response = {"status": "registered", "client_id": client_id}
                        client_socket.send(json.dumps(response).encode())
                        
                    elif message['action'] == 'get_system_info':
                        response = {"system_info": {"os": "Server", "status": "active"}}
                        client_socket.send(json.dumps(response).encode())
                        
                except socket.timeout:
                    continue
                except ConnectionResetError:
                    print(f"🔒 Соединение с клиентом {client_id} разорвано")
                    break
                except BrokenPipeError:
                    print(f"🔒 Соединение с клиентом {client_id} разорвано (Broken Pipe)")
                    break
                except Exception as e:
                    print(f"❌ Ошибка с клиентом {client_id}: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ Критическая ошибка с клиентом {client_id}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            with self.clients_lock:
                if client_id in self.connected_clients:
                    del self.connected_clients[client_id]
            print(f"🔒 Клиент {client_id} отключен")

    def get_connected_clients_count(self):
        """Возвращает количество подключенных клиентов"""
        with self.clients_lock:
            return len(self.connected_clients)
    
    def get_connected_clients_info(self):
        """Возвращает информацию о подключенных клиентах (без socket объектов)"""
        clients_info = {}
        with self.clients_lock:
            for client_id, client_info in self.connected_clients.items():
                clients_info[client_id] = {
                    'address': client_info['address'],
                    'connected_at': client_info['connected_at'],
                    'last_activity': client_info.get('last_activity', 0),
                    'system_info': client_info.get('system_info', {})
                }
        return clients_info
    
    def get_client_socket(self, client_id):
        """Безопасно получает socket клиента"""
        with self.clients_lock:
            if client_id in self.connected_clients:
                return self.connected_clients[client_id]['socket']
        return None

    def start_server(self):
        """Запускает сервер"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"✅ Сервер запущен на {self.host}:{self.port}")
            print("⏳ Ожидание подключения клиентов...")
            
            client_counter = 1
            while True:
                client_socket, address = server_socket.accept()
                print(f"🔗 Новое подключение от {address}")
                
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address, f"client_{client_counter}")
                )
                client_thread.daemon = True
                client_thread.start()
                client_counter += 1
                
        except Exception as e:
            print(f"❌ Ошибка сервера: {e}")
        finally:
            try:
                server_socket.close()
            except:
                pass