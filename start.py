import os
import sys
import json
import hashlib
import requests
import subprocess
from colorama import Fore, init
from tqdm import tqdm

init(autoreset=True)

REPO_URL = "https://raw.githubusercontent.com/devpaket/PaketBet/main/"
VERSION_FILE = "version.txt"
MANIFEST_FILE = "manifest.json"

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

def calculate_hash(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(4096):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def get_local_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    return "0.0"

def get_remote_version():
    try:
        response = requests.get(REPO_URL + VERSION_FILE, timeout=10)
        response.raise_for_status()
        return response.text.strip()
    except:
        return None

def download_file_with_progress(url, save_path):
    try:
        # Нормализация пути для Windows
        save_path = os.path.normpath(save_path)
        
        # Создаем директорию, только если она указана
        dir_name = os.path.dirname(save_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, 
                                 desc=os.path.basename(save_path)) as t:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            t.total = total_size
            
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
                        t.update(len(chunk))
        return True
    except Exception as e:
        print(f"{Fore.RED}Ошибка загрузки {save_path}: {str(e)}")
        return False

def should_update():
    local = get_local_version()
    remote = get_remote_version()
    
    if not remote:
        print(f"{Fore.YELLOW}Не удалось проверить обновления")
        return False
    
    if remote == local:
        print(f"{Fore.GREEN}Текущая версия {local} актуальна")
        return False
    
    print(f"{Fore.CYAN}Доступна новая версия: {remote} (текущая: {local})")
    choice = input(f"{Fore.YELLOW}Установить обновление? [Y/n]: ").strip().lower()
    return choice in ('', 'y', 'yes')

def update_files():
    try:
        print(f"\n{Fore.YELLOW}🔄 Проверка обновлений...")

        # Загрузка манифеста
        manifest_url = REPO_URL + MANIFEST_FILE
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        manifest = json.loads(response.text)
        
        files_to_update = []
        for file_info in manifest["files"]:
            file_path = os.path.normpath(file_info["path"])
            
            if file_path in ["config.py", "casino_log.db", "reffelal.db"]:
                continue
            
            current_hash = calculate_hash(file_path)
            if not current_hash or current_hash != file_info["hash"]:
                files_to_update.append(file_info)
        
        if not files_to_update:
            print(f"{Fore.GREEN}✓ Все файлы актуальны")
            return True
        
        print(f"{Fore.CYAN}📦 Найдено {len(files_to_update)} файлов для обновления")
        
        success = True
        for file_info in files_to_update:
            file_path = os.path.normpath(file_info["path"])
            file_url = REPO_URL + file_info["path"].replace('\\', '/')
            
            print(f"\n{Fore.CYAN}⬇️ Загрузка {file_path}...")
            if not download_file_with_progress(file_url, file_path):
                success = False
        
        # Обновляем version.txt вручную, если всё успешно
        if success:
            remote_version = get_remote_version()
            if remote_version:
                with open(VERSION_FILE, "w") as f:
                    f.write(remote_version)
                print(f"\n{Fore.GREEN}🎉 Обновление до версии {remote_version} завершено!")
            else:
                print(f"\n{Fore.YELLOW}⚠ Не удалось получить удалённую версию для записи")
        else:
            print(f"\n{Fore.YELLOW}⚠ Обновление завершено с ошибками")
        
        return success
    
    except Exception as e:
        print(f"\n{Fore.RED}⛔ Ошибка при обновлении: {str(e)}")
        return False

def main():
    if should_update():
        update_files()
    
    print(f"\n{Fore.CYAN}🚀 Запуск основного скрипта...")
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}⛔ Ошибка запуска main.py: {e}")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Работа бота завершена")

if __name__ == "__main__":
    main()
