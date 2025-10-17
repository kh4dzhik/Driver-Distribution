# admin_console.py
import os
import json
import shutil
from server_admin import DriverDeploymentServer
import threading
import time

#for tkinter
import customtkinter as ctk
from tkinter import filedialog, messagebox
from CTkListbox import * # for List

import pywinstyles
from functools import partial

class AdminConsole:
    def __init__(self):
        self.server = DriverDeploymentServer()
        self.server_thread = None
        self.selected_clients = None
        self.selected_drivers = None
        self.selected_id = []

    def init_tkinter(self):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        app = ctk.CTk()
        app.title("Driver Distribution")
        app.geometry("600x400")
        app.resizable(False, False)
        return app

    def start_server_background(self):
        """Запускает сервер в фоновом режиме"""
        def run_server():
            self.server.start_server()
        
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        time.sleep(1)  # Даем серверу время на запуск
    
    def show_menu(self):
        print("\n" + "="*50)
        print("=== ЦЕНТРАЛИЗОВАННОЕ УПРАВЛЕНИЕ ДРАЙВЕРАМИ ===")
        print("1. Показать подключенные клиенты")
        print("2. Загрузить драйвер на сервер")
        print("3. Развернуть драйвер на всех клиентах")
        print("4. Развернуть драйвер на конкретном клиенте")
        print("5. Показать историю развертываний")
        print("6. Создать тестовые драйверы")
        print("7. Выйти")
        print("="*50)
    
    def show_connected_clients(self):
        """Показывает подключенных клиентов"""
        clients = self.server.get_connected_clients_info()
        print(f"\n📊 Подключенные клиенты: {len(clients)}")
        for client_id, client_info in clients.items():
            system_info = client_info.get('system_info', {})
            os_name = system_info.get('os', 'unknown')
            print(f"   - {client_id}: {os_name} ({client_info['address']})")
    
    def upload_driver(self, pPath, pList):
        """Только администратор загружает драйверы"""
        driver_paths = pPath
        for pPath in driver_paths:
            if os.path.exists(pPath):
                # Копируем в центральное хранилище
                target_path = os.path.join(self.server.drivers_dir, os.path.basename(pPath))
                shutil.copy2(pPath, target_path)
                print(f"✅ Драйвер загружен: {os.path.basename(pPath)}")
                self.update_drivers_list(pList)
            else:
                print("❌ Файл не найден")
    
    def create_test_drivers(self):
        """Создает тестовые драйверы"""
        test_drivers = [
            {"name": "nvidia_windows.exe", "content": "NVIDIA Driver for Windows"},
            {"name": "amd_linux.deb", "content": "AMD Driver for Linux"}, 
            {"name": "intel_network.inf", "content": "Intel Network Driver"},
            {"name": "realtek_audio_windows.zip", "content": "Realtek Audio Driver"}
        ]
        
        for driver in test_drivers:
            path = os.path.join(self.server.drivers_dir, driver["name"])
            with open(path, 'w') as f:
                f.write(driver["content"])
        
        print("✅ Тестовые драйверы созданы:")
        for driver in test_drivers:
            print(f"   - {driver['name']}")
    
    def show_drivers_list(self):
        """Показывает список драйверов"""
        drivers = self.server.get_driver_list()
        print(f"\n📦 Доступные драйверы: {len(drivers)}")
        for i, driver in enumerate(drivers, 1):
            print(f"   {i}. {driver['name']} ({driver['size']} байт)")
        return drivers
    
    def mass_deploy(self):
        """Массовое развертывание выбранного драйвера"""
        if self.server.get_connected_clients_count() == 0:
            print("❌ Нет подключенных клиентов")
            return
            
        drivers = self.show_drivers_list()
        if not drivers:
            print("❌ Нет доступных драйверов")
            return
            
        try:
            choice = int(input("Выберите драйвер: ")) - 1
            if 0 <= choice < len(drivers):
                driver_name = drivers[choice]['name']
                print(f"🔄 Развертывание {driver_name} на всех клиентах...")
                results = self.server.mass_deploy(driver_name)
                
                print("\n📊 Результаты развертывания:")
                for client, result in results.items():
                    status_icon = "✅" if result['status'] == 'success' else "❌"
                    if result['status'] == 'skipped':
                        status_icon = "⚠️"
                    print(f"   {status_icon} {client}: {result['status']} - {result.get('message', '')}")
            else:
                print("❌ Неверный выбор")
        except ValueError:
            print("❌ Введите число")
    
    def deploy_to_specific_client(self):
        """Развертывание на конкретном клиенте"""
        clients = self.server.get_connected_clients_info()
        if not clients:
            print("❌ Нет подключенных клиентов")
            return
            
        print("\n📋 Подключенные клиенты:")
        client_list = list(clients.keys())
        for i, client_id in enumerate(client_list, 1):
            print(f"   {i}. {client_id}")
            
        try:
            client_choice = int(input("Выберите клиента: ")) - 1
            if 0 <= client_choice < len(client_list):
                client_id = client_list[client_choice]
                
                # Получаем socket клиента
                client_socket = self.server.get_client_socket(client_id)
                if not client_socket:
                    print("❌ Клиент отключился")
                    return
                    
                drivers = self.show_drivers_list()
                
                if drivers:
                    driver_choice = int(input("Выберите драйвер: ")) - 1
                    if 0 <= driver_choice < len(drivers):
                        driver_name = drivers[driver_choice]['name']
                        print(f"🔄 Развертывание {driver_name} на {client_id}...")
                        
                        result = self.server.deploy_to_client(client_socket, driver_name)
                        
                        status_icon = "✅" if result['status'] == 'success' else "❌"
                        print(f"   {status_icon} Результат: {result['status']} - {result.get('message', '')}")
                    else:
                        print("❌ Неверный выбор драйвера")
                else:
                    print("❌ Нет доступных драйверов")
            else:
                print("❌ Неверный выбор клиента")
        except ValueError:
            print("❌ Введите число")
    
    def update_client_list(self, pList):
        pList.delete("all")
        clients = self.server.get_connected_clients_info()

        for client_id, client_info in clients.items():
            system_ip = client_info.get('address')
            pList.insert(client_id, system_ip)

    def update_drivers_list(self, pList):
        drivers = self.server.get_driver_list()
        #print(f"\n📦 Доступные драйверы: {len(drivers)}")
        
        # for i, driver in enumerate(drivers, 1):
        #     print(f"   {i}. {driver['name']} ({driver['size']} байт)")

        for i, driver in enumerate(drivers, 1):
            pList.insert(i, f"{driver['name']} {driver['size']} байт")

    def get_client_id_by_ip(self, ip_address: str) -> str | None:
        """Возвращает client_id по IP-адресу клиента"""
        with self.server.clients_lock:
            for client_id, client_info in self.server.connected_clients.items():
                client_ip = client_info['address'][0]  # адрес вида (ip, port)
                if client_ip == ip_address:
                    return client_id
        return None

    def show_value(self, selected_option):
        print(selected_option)

    def save_value_users(self, selected_option):
        self.selected_clients = selected_option

    def save_value_drivers(self, selected_option):
        self.selected_drivers = selected_option
        
    def deploy_driver_to_clients(self):
        if not self.selected_clients or not self.selected_drivers:
            messagebox.showwarning("Предупреждение", "Выберите клиентов и драйверы для установки")
            return
            
        self.selected_id = []
        clients = self.server.get_connected_clients_info()

        # Собираем ID выбранных клиентов
        for client_id, client_info in clients.items():
            system_ip = client_info.get('address')
            for client_ip in self.selected_clients:
                if client_ip == system_ip:
                    self.selected_id.append(client_id)
        
        if not self.selected_id:
            messagebox.showwarning("Предупреждение", "Выбранные клиенты не найдены или отключились")
            return
            
        print(f"🎯 Установка драйверов на клиентов: {self.selected_id}")
        
        # Создаем диалог прогресса
        progress_window = ctk.CTkToplevel()
        progress_window.title("Установка драйверов")
        progress_window.geometry("400x200")
        progress_window.transient(self.init_tkinter())
        progress_window.grab_set()
        
        progress_label = ctk.CTkLabel(progress_window, text="Начинаю установку драйверов...", font=("Arial", 14))
        progress_label.pack(pady=20)
        
        progress_bar = ctk.CTkProgressBar(progress_window, width=300)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        results_text = ctk.CTkTextbox(progress_window, width=350, height=100)
        results_text.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Запускаем установку в отдельном потоке
        def run_deployment():
            total_operations = len(self.selected_id) * len(self.selected_drivers)
            completed_operations = 0
            
            for client_id in self.selected_id:
                client_socket = self.server.get_client_socket(client_id)
                if not client_socket:
                    results_text.insert("end", f"❌ Клиент {client_id} отключился\n")
                    results_text.see("end")
                    completed_operations += len(self.selected_drivers)
                    continue
                    
                for driver_name in self.selected_drivers:
                    try:
                        results_text.insert("end", f"🔄 Установка {driver_name} на {client_id}...\n")
                        results_text.see("end")
                        progress_window.update()
                        
                        result = self.server.deploy_to_client(client_socket, driver_name)
                        
                        status_icon = "✅" if result['status'] == 'success' else "❌"
                        if result['status'] == 'skipped':
                            status_icon = "⚠️"
                            
                        results_text.insert("end", f"{status_icon} {client_id}: {result['status']} - {result.get('message', '')}\n")
                        results_text.see("end")
                        
                    except Exception as e:
                        results_text.insert("end", f"❌ Ошибка: {str(e)}\n")
                        results_text.see("end")
                    
                    completed_operations += 1
                    progress = completed_operations / total_operations
                    progress_bar.set(progress)
                    progress_label.configure(text=f"Прогресс: {completed_operations}/{total_operations}")
                    progress_window.update()
            
            progress_label.configure(text="Установка завершена!")
            close_button = ctk.CTkButton(progress_window, text="Закрыть", command=progress_window.destroy)
            close_button.pack(pady=10)
        
        # Запускаем поток установки
        deployment_thread = threading.Thread(target=run_deployment)
        deployment_thread.daemon = True
        deployment_thread.start()

    def run(self):
        """Запускает административную консоль"""
        print("🚀 Запуск системы управления драйверами...")
        self.start_server_background()
        self.create_test_drivers()  # Создаем тестовые драйверы
        pApp = self.init_tkinter()

        # Работа с ткинтером
        clientList = CTkListbox(pApp, command=self.save_value_users, width=200, height=100, multiple_selection=True)
        clientList.place(x=20, y=50)

        update_button = ctk.CTkButton(pApp, text="Обновить", command=lambda: self.update_client_list(clientList))
        update_button.place(x=20, y=200)

        list_label = ctk.CTkLabel(pApp, text="Список Устройств", font=("Arial", 16))
        list_label.place(x=20, y=30)

        driverList = CTkListbox(pApp, command=self.save_value_drivers, width=200, height=100, multiple_selection=True)
        driverList.place(x=350, y=50)
        
        # Drag and drop функционал из первого кода
        wrapper_func = partial(self.upload_driver, pList=driverList)
        pywinstyles.apply_dnd(driverList, wrapper_func)
        
        self.update_drivers_list(driverList)

        driver_list_label = ctk.CTkLabel(pApp, text="Доступные драйверы", font=("Arial", 16))
        driver_list_label.place(x=350, y=30)
        driver_list_label2 = ctk.CTkLabel(pApp, text="Перетащите файлы сюда", font=("Arial", 12))
        driver_list_label2.place(x=350, y=175)

        deploy_button = ctk.CTkButton(pApp, text="Установить драйверы", command=self.deploy_driver_to_clients)
        deploy_button.place(x=350, y=200)

        # Добавляем кнопку очистки выбора
        clear_button = ctk.CTkButton(pApp, text="Очистить выбор", command=lambda: self.clear_selection(clientList, driverList))
        clear_button.place(x=20, y=240)

        pApp.mainloop()

    def clear_selection(self, client_list, driver_list):
        """Очищает выбранные клиенты и драйверы"""
        client_list.deselect("all")
        driver_list.deselect("all")
        self.selected_clients = None
        self.selected_drivers = None
        print("✅ Выбор очищен")

if __name__ == "__main__":
    admin = AdminConsole()
    admin.run()