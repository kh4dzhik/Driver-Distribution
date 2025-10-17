# client_agent.py
import socket
import json
import platform
import subprocess
import os
import time

class DriverClientAgent:
    def __init__(self, server_host=None, server_port=8888, client_name=None):
        # Читаем конфиг и устанавливаем параметры
        config = self.load_config()
        self.server_host = server_host or config.get('server_host', 'localhost')
        self.server_port = server_port or config.get('server_port', 8888)
        self.client_name = client_name or config.get('client_name') or f"client_{platform.node()}"
        self.system_info = self.collect_system_info()
        self.client_id = None
        
    def load_config(self):
        """Загружает конфигурацию из файла config.json"""
        config_path = "config.json"
        default_config = {
            "server_host": "localhost",
            "server_port": 8888,
            "client_name": f"client_{platform.node()}"
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"✅ Конфигурация загружена из {config_path}")
                return config
            else:
                # Создаем файл с конфигурацией по умолчанию
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                print(f"📁 Создан файл конфигурации {config_path}")
                print("⚠️  Пожалуйста, укажите IP-адрес сервера в config.json")
                return default_config
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return default_config
    
    def collect_system_info(self):
        """Собирает информацию о системе"""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "processor": platform.processor()
        }
    
    def install_driver(self, driver_path):
        """Устанавливает драйвер и возвращает результат"""
        installer_path = driver_path
        
        print(f"🔄 [{self.client_name}] Запуск установки: {os.path.basename(installer_path)}")
        
        # Используем только флаг /S
        install_command = [installer_path, "/S"]
        
        try:
            print(f"💻 [{self.client_name}] Установка с флагом /S")
            result = subprocess.run(
                install_command, 
                check=True,
                capture_output=True,
                text=True,
                timeout=120  # 2 минуты на установку
            )
            
            print(f"✅ [{self.client_name}] Драйвер успешно установлен!")
            return {
                "status": "success", 
                "message": "Драйвер установлен успешно"
            }
            
        except subprocess.CalledProcessError as e:
            # Код 2 - нормальное завершение установки для некоторых драйверов
            if e.returncode == 2:
                print(f"✅ [{self.client_name}] Драйвер установлен успешно (код завершения 2)")
                return {
                    "status": "success", 
                    "message": "Драйвер установлен успешно"
                }
            else:
                print(f"❌ [{self.client_name}] Ошибка установки: {e.returncode}")
                return {
                    "status": "failed", 
                    "message": f"Установка завершилась с кодом {e.returncode}. Попробуйте установить вручную."
                }
                
        except subprocess.TimeoutExpired:
            print(f"⏰ [{self.client_name}] Таймаут установки")
            return {
                "status": "error", 
                "message": "Таймаут при установке драйвера"
            }
                
        except Exception as e:
            print(f"❌ [{self.client_name}] Критическая ошибка установки: {e}")
            return {
                "status": "error", 
                "message": f"Критическая ошибка: {str(e)}"
            }
    
    def safe_json_decode(self, data):
        """Безопасно декодирует JSON данные"""
        try:
            if isinstance(data, bytes):
                # Пытаемся декодировать как UTF-8
                try:
                    text = data.decode('utf-8').strip()
                except UnicodeDecodeError:
                    # Если не UTF-8, пробуем другие кодировки
                    try:
                        text = data.decode('latin-1').strip()
                    except:
                        text = data.decode('utf-8', errors='ignore').strip()
            else:
                text = str(data).strip()
            
            if not text:
                return None
            
            # Убираем возможные лишние символы в начале/конце
            text = text.strip()
            
            # Проверяем, что строка начинается с { и заканчивается }
            if not text.startswith('{') or not text.endswith('}'):
                print(f"⚠️ [{self.client_name}] Невалидный JSON формат: {text[:100]}")
                return None
                
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            print(f"❌ [{self.client_name}] Ошибка JSON: {e}")
            print(f"📄 [{self.client_name}] Данные: {data[:200] if data else 'empty'}")
            return None
        except Exception as e:
            print(f"❌ [{self.client_name}] Ошибка декодирования: {e}")
            return None
    
    def receive_file_data(self, client_socket, total_size):
        """Принимает файловые данные"""
        received_data = b""
        received_size = 0
        
        print(f"📥 [{self.client_name}] Начинаю загрузку файла ({total_size} байт)...")
        
        client_socket.settimeout(30.0)  # Увеличиваем таймаут для больших файлов
        
        while received_size < total_size:
            try:
                chunk = client_socket.recv(min(8192, total_size - received_size))
                if not chunk:
                    break
                received_data += chunk
                received_size += len(chunk)
                
                # Прогресс загрузки
                if received_size % (1024 * 1024) == 0:  # Каждые 1MB
                    progress = (received_size / total_size) * 100
                    print(f"📥 [{self.client_name}] Загружено: {received_size}/{total_size} байт ({progress:.1f}%)")
                    
            except socket.timeout:
                print(f"⏰ [{self.client_name}] Таймаут при получении файла")
                break
            except Exception as e:
                print(f"❌ [{self.client_name}] Ошибка получения файла: {e}")
                break
                
        print(f"📥 [{self.client_name}] Загрузка завершена: {received_size}/{total_size} байт")
        return received_data
    
    def handle_server_commands(self, client_socket):
        """Обрабатывает команды от сервера"""
        try:
            while True:
                client_socket.settimeout(2.0)
                
                try:
                    data = client_socket.recv(8192)  # Увеличиваем буфер
                    if not data:
                        print(f"📡 [{self.client_name}] Сервер закрыл соединение")
                        break
                    
                    message = self.safe_json_decode(data)
                    if not message:
                        # Если это не JSON, возможно это файловые данные
                        if len(data) > 100:  # Если данные большие, скорее всего файл
                            print(f"📦 [{self.client_name}] Получены бинарные данные ({len(data)} байт)")
                        continue
                    
                    action = message.get('action', 'unknown')
                    print(f"📨 [{self.client_name}] Команда от сервера: {action}")
                    
                    if action == 'get_system_info':
                        response = {"system_info": self.system_info}
                        client_socket.send(json.dumps(response).encode())
                        
                    elif action == 'install_driver':
                        driver_name = message.get('driver_name', 'unknown')
                        print(f"🔄 [{self.client_name}] Начинаю установку драйвера: {driver_name}")
                        
                        result = self.receive_and_install_driver(client_socket, driver_name)
                        
                        # Отправляем результат обратно серверу
                        print(f"📤 [{self.client_name}] Отправляю результат установки")
                        response_data = json.dumps(result).encode()
                        client_socket.send(response_data)
                        
                    else:
                        print(f"❓ [{self.client_name}] Неизвестная команда: {action}")
                        
                except socket.timeout:
                    continue
                except BlockingIOError:
                    continue
                except ConnectionResetError:
                    print(f"🔒 [{self.client_name}] Соединение разорвано сервером")
                    break
                except Exception as e:
                    print(f"❌ [{self.client_name}] Ошибка обработки команды: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ [{self.client_name}] Критическая ошибка: {e}")
    
    def receive_and_install_driver(self, client_socket, driver_name: str):
        """Принимает и устанавливает драйвер с сервера"""
        try:
            # Получаем информацию о файле
            client_socket.settimeout(10.0)
            file_info_data = client_socket.recv(2048)  # Увеличиваем буфер для метаданных
            
            file_info = self.safe_json_decode(file_info_data)
            if not file_info:
                return {"status": "error", "message": "Не удалось получить информацию о файле"}
            
            print(f"📦 [{self.client_name}] Информация о файле: {file_info['name']}, размер: {file_info['size']} байт")
            
            # Подтверждаем получение информации
            client_socket.send(b'ACK')
            
            # Получаем данные файла
            received_data = self.receive_file_data(client_socket, file_info['size'])

            if len(received_data) != file_info['size']:
                print(f"❌ [{self.client_name}] Получено {len(received_data)} байт вместо {file_info['size']}")
                return {"status": "error", "message": "Неполный файл"}

            # Сохраняем файл
            os.makedirs("drivers", exist_ok=True)
            file_path = os.path.join("drivers", file_info['name'])
            
            with open(file_path, 'wb') as f:
                f.write(received_data)

            print(f"✅ [{self.client_name}] Файл сохранен: {file_path}")

            # Устанавливаем драйвер
            print(f"🔄 [{self.client_name}] Запускаю установку драйвера...")
            install_result = self.install_driver(file_path)
            
            # Очищаем временный файл
            try:
                os.remove(file_path)
                print(f"🧹 [{self.client_name}] Временный файл удален")
            except Exception as e:
                print(f"⚠️ [{self.client_name}] Не удалось удалить временный файл: {e}")
            
            return install_result
                
        except socket.timeout:
            return {"status": "error", "message": "Таймаут при получении файла"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def start(self):
        """Запускает клиентский агент"""
        print(f"🚀 [{self.client_name}] Запуск клиента...")
        print(f"🔧 [{self.client_name}] Система: {self.system_info['os']} {self.system_info['architecture']}")
        print(f"🌐 [{self.client_name}] Подключение к серверу: {self.server_host}:{self.server_port}")
        
        while True:
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(5.0)
                print(f"🔌 [{self.client_name}] Подключаюсь к {self.server_host}:{self.server_port}...")
                client_socket.connect((self.server_host, self.server_port))
                print(f"✅ [{self.client_name}] Подключен к серверу {self.server_host}:{self.server_port}")
                
                # Регистрируемся на сервере
                registration = {
                    "action": "register_client",
                    "system_info": self.system_info,
                    "client_name": self.client_name
                }
                client_socket.send(json.dumps(registration).encode())
                
                # Получаем подтверждение
                response_data = client_socket.recv(1024)
                response = self.safe_json_decode(response_data)
                
                if response and response.get('status') == 'registered':
                    print(f"📝 [{self.client_name}] Успешно зарегистрирован на сервере")
                    if 'client_id' in response:
                        self.client_id = response['client_id']
                        print(f"🆔 [{self.client_name}] ID клиента: {self.client_id}")
                else:
                    print(f"❌ [{self.client_name}] Ошибка регистрации: {response}")
                    client_socket.close()
                    time.sleep(5)
                    continue
                
                # Обрабатываем команды сервера
                self.handle_server_commands(client_socket)
                
            except socket.timeout:
                print(f"⏰ [{self.client_name}] Таймаут подключения к серверу")
            except ConnectionRefusedError:
                print(f"❌ [{self.client_name}] Сервер недоступен по адресу {self.server_host}:{self.server_port}")
            except Exception as e:
                print(f"❌ [{self.client_name}] Ошибка подключения: {e}")
            
            print(f"🔄 [{self.client_name}] Переподключение через 5 секунд...")
            time.sleep(5)

if __name__ == "__main__":
    import sys
    client_name = sys.argv[1] if len(sys.argv) > 1 else None
    client = DriverClientAgent(client_name=client_name)
    client.start()