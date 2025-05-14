# database.py
import sqlite3
from config import LOG_FILE, REFERRAL_FILE

class Database:
    def __init__(self):
        # Основная БД (users)
        self.main_conn = sqlite3.connect('casino_bot.db', check_same_thread=False)
        self._init_main_db()
        
        # БД логов
        self.log_conn = sqlite3.connect(LOG_FILE, check_same_thread=False)
        self._init_log_db()
        
        # БД рефералов
        self.referral_conn = sqlite3.connect(REFERRAL_FILE, check_same_thread=False)
        self._init_referral_db()

    def _init_main_db(self):
        self.main_conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, 
                balance REAL DEFAULT 0
            )
        ''')
        self.main_conn.commit()

    def _init_log_db(self):
        self.log_conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                amount REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.log_conn.commit()

    def _init_referral_db(self):
        self.referral_conn.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_user_id INTEGER,
                referral_code TEXT UNIQUE,
                referred_user_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.referral_conn.commit()

    def get_main_cursor(self):
        return self.main_conn.cursor()

    def get_log_cursor(self):
        return self.log_conn.cursor()

    def get_referral_cursor(self):
        return self.referral_conn.cursor()

# Создаём экземпляр БД при импорте
db = Database()