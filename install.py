import os
import sys
from colorama import Fore, init

init(autoreset=True)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    banner = f"""
    {Fore.CYAN}╔═╗╔═╗╔╦╗╔═╗╦ ╦╔╦╗╔═╗╦═╗╔╦╗
    {Fore.BLUE}╠═╝║ ║ ║ ║  ╠═╣║║║║ ║╠╦╝ ║ 
    {Fore.MAGENTA}╩  ╚═╝ ╩ ╚═╝╩ ╩╩ ╩╚═╝╩╚═ ╩ 
    {Fore.WHITE}Автоматический установщик v1.0
    """
    print(banner)

def check_dependencies():
    required = ['aiogram', 'aiocryptopay', 'pillow', 'colorama']
    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    return missing

def create_config():
    config = '''# Конфигурационный файл бота

# Токены
API_TOKEN = "{api_token}"
CRYPTOPAY_API_TOKEN = "{cryptopay_token}"

# Администрация
admin_id = {admin_id}
moder_id = [{moder_id}]

# Настройки игр
coefficient = 0.8
coof7 = 9
coof3 = 4
box_cof = 1

# Базы данных
LOG_FILE = 'casino_log.db'
REFERRAL_FILE = "reffelal.db"

# Каналы
win_id = {win_id}
win_Name = "{win_name}"
win_Link = "{win_link}"
Sub_Id = {sub_id}
Sub_Name = "{sub_name}"
Sub_Link = "{sub_link}"
chat_id_log = {log_chat}

# Юзернеймы
BOT_USERNAME = '{bot_username}'
ADMIN_USERNAME = '{admin_username}'
'''

    print(f"{Fore.YELLOW}\n🛠 Заполнение конфигурации...")
    
    data = {
        'api_token': input("Введите Telegram API токен бота: "),
        'cryptopay_token': input("Введите CryptoPay API токен: "),
        'admin_id': int(input("ID главного администратора: ")),
        'moder_id': input("ID модераторов (через запятую): "),
        'win_id': int(input("ID игрового канала (с -100): ")),
        'win_name': input("Название игрового канала: "),
        'win_link': input("Ссылка на игровой канал: "),
        'sub_id': int(input("ID спонсорского канала (с -100): ")),
        'sub_name': input("Название спонсорского канала: "),
        'sub_link': input("Ссылка на спонсорский канал: "),
        'log_chat': int(input("ID чата для логов (с -100): ")),
        'bot_username': input("Юзернейм бота (@username): ").replace('@', ''),
        'admin_username': input("Юзернейм админа (@username): ").replace('@', '')
    }

    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(config.format(**data))
    
    print(f"{Fore.GREEN}✓ Конфиг успешно создан!")

def main():
    clear_screen()
    print_banner()
    
    missing = check_dependencies()
    if missing:
        print(f"{Fore.RED}✗ Отсутствуют зависимости: {', '.join(missing)}")
        if input("Установить автоматически? (y/n): ").lower() == 'y':
            os.system(f"{sys.executable} -m pip install {' '.join(missing)}")
    
    if not os.path.exists('config.py'):
        create_config()
    else:
        print(f"{Fore.YELLOW}⚠ Конфигурационный файл уже существует!")
    
    print(f"{Fore.CYAN}\n🎉 Установка завершена! Запустите бота:")
    print(f"{Fore.WHITE}python main.py")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"{Fore.RED}⛔ Ошибка: {str(e)}")
    input("\nНажмите Enter для выхода...")