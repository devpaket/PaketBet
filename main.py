import asyncio
import os
import random
import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont
from aiocryptopay import AioCryptoPay, Networks
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, \
    KeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import keyboard

# Настройки бота
API_TOKEN = config.API_TOKEN
CRYPTO_API_TOKEN = config.CRYPTOPAY_API_TOKEN

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

processed_invoices = []

# Инициализация CryptoPay
cryptopay = AioCryptoPay(token=CRYPTO_API_TOKEN, network=Networks.TEST_NET)

# Инициализация базы данных
conn = sqlite3.connect('casino_bot.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
              (user_id INTEGER PRIMARY KEY, balance REAL)''')
conn.commit()

# Инициализация базы данных для логов
log_conn = sqlite3.connect(config.LOG_FILE)
log_cursor = log_conn.cursor()
log_cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        amount REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
log_conn.commit()

referral_conn = sqlite3.connect(config.REFERRAL_FILE)
referral_cursor = referral_conn.cursor()

# Создаем таблицу referrals, если она не существует
referral_cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_user_id INTEGER, 
        referral_code TEXT,
        referred_user_id INTEGER,
        status TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Сохраняем изменения
referral_conn.commit()

prefixes = [
    {"name": "<b>🎰 Лудик</b>", "description": "Король рисковых ставок и вечный участник лудоманских приключений!",
     "price": 500},
    {"name": "<i>💸Сливер</i>", "description": "Гуру сливов, но всегда с оптимизмом и надеждой на лучшее!",
     "price": 100},
    {"name": "<u>🔥 Жареный</u>", "description": "Всегда на пике азарта! Сгорает в каждом раунде, но не сдаётся!",
     "price": 1500},
    {"name": "<b>💀 Жесткий Фарт</b>",
     "description": "Везунчик со странной судьбой: удача улыбается, но с суровым взглядом.", "price": 3000},
    {"name": "<i>🕹️ Рулетка</i>", "description": "Крутится-вертится шарик! Мастер ставок и фартовых комбинаций.",
     "price": 700},
    {"name": "<u>💣 Мелстрой</u>", "description": "Легенда стримов и ставок. Удача или проигрыш? Вопрос времени.",
     "price": 20000},
    {"name": "<b>💰 Счастливчик</b>", "description": "Настоящий счастливчик! Улыбка удачи никогда не покидает его.",
     "price": 1200},
    {"name": "<i>🤑 Миллионер</i>", "description": "Всегда мечтает о миллионах, и пусть виртуальных, но своих!",
     "price": 5000},
    {"name": "<b>🎲 Фартовый Бро</b>", "description": "Бро, которому всегда фартит! Любит риск и выигрыши.",
     "price": 900},
    {"name": "<u>💥 Заносер</u>", "description": "Тот, кто всегда 'заносит' крупные суммы. Всегда на пике успеха!",
     "price": 10000},
    {"name": "🔔 Игрок", "description": "Префикс по умолчанию", "price": 0},
    {"name": "<i>👻 Бомжара</i>", "description": "Тот кто проебал всю жизнь в казике. Но это не повод расстраиваться!",
     "price": 50}

]


# Пример вывода информации о префиксе


def get_user_prefix(user_id):
    conn = sqlite3.connect('casino_bot.db')
    cursor = conn.cursor()

    # Извлекаем ID префикса
    cursor.execute("SELECT prefix_id FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()  # Получаем результат

    conn.close()

    if result:
        return result[0]  # Возвращаем ID префикса

    else:
        return None  # Если пользователь не найден или у него нет префикса


def log_action(user_id, action, amount):
    log_cursor.execute("INSERT INTO logs (user_id, action, amount) VALUES (?, ?, ?)",
                       (user_id, action, amount))
    log_conn.commit()


async def notify_admins(message):
    chat_id = config.chat_id_log
    await bot.send_message(chat_id, message, parse_mode="HTML")


def generate_referral_code(user_id):
    return f"{user_id}"


def generate_referral_link(user_id):
    referral_code = generate_referral_code(user_id)
    return f"https://t.me/{config.BOT_USERNAME}?start={referral_code}"


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    if is_user_locked(user_id):
        await message.answer(f"Вы были заблокированы t.me/{config.ADMIN_USERNAME}")
        return

    user_id = message.from_user.id
    referral_code = None
    check_code = None

    # Извлечение аргументов из команды
    args = message.text.split(maxsplit=1)  # Разделяем по пробелам

    if len(args) > 1:  # Если есть аргументы
        param = args[1]  # Получаем второй элемент (аргумент)

        if param.startswith("check_"):
            check_code = param.split("_")[1]  # Извлекаем код чека
        else:
            referral_code = param  # Обработка реферального кода

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    # Проверка подписки на канал
    chat_member = await bot.get_chat_member(chat_id=config.win_id, user_id=user_id)
    chat_member2 = await bot.get_chat_member(chat_id=config.Sub_Id, user_id=user_id)

    if chat_member.status not in ['member', 'administrator', 'creator'] or chat_member2.status not in ['member',
                                                                                                       'administrator',
                                                                                                       'creator']:
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰{config.win_Name}", url=f"{config.win_Link}")],
            [InlineKeyboardButton(text=f"{config.Sub_Name}", url=f"{config.Sub_Link}")]

        ])

        await message.answer("Чтобы продолжить, пожалуйста, подпишитесь на наш канал:", reply_markup=inline_keyboard)
        return

    # Регистрация пользователя, если он не зарегистрирован
    if user is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 100))
        cursor.execute("UPDATE users SET prefix_id = 10 WHERE user_id = ?", (user_id,))
        conn.commit()
        log_action(user_id, "Registration", 100)
        photo = FSInputFile('res/profile.jpg')
        await bot.send_photo(
            chat_id=message.from_user.id,
            caption="🎰 Добро пожаловать в наше казино! Ваш аккаунт создан и на баланс зачислено 100 USDT.\n/help для помощи",
            photo=photo)

    # Проверяем наличие чека
    if check_code:
        await claim_check(message)  # Передаем код чека

    # Обработка реферального кода, если он есть
    if referral_code:
        referral_cursor.execute("SELECT * FROM referrals WHERE referral_code=?", (referral_code,))
        referral_record = referral_cursor.fetchone()

        if referral_record:
            referrer_id = referral_record[1]
            # Проверка, не был ли уже добавлен этот реферал
            if referral_record[3] is None:
                # Обновляем запись в таблице рефералов и начисляем бонусы
                referral_cursor.execute(
                    "UPDATE referrals SET referred_user_id=?, status=? WHERE referral_code=?",
                    (user_id, "completed", referral_code)
                )
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (150, referrer_id))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (100, user_id))
                referral_conn.commit()

                # Уведомление пригласившего пользователя
                try:
                    await bot.send_message(referrer_id,
                                           f"🎉 У вас новый реферал: @{message.from_user.username}!\nВы получили 150 USDT.")
                    print(f"Referral message sent to: {referrer_id}")  # Логирование для отладки
                except Exception as e:
                    print(f"Failed to send message to referrer: {e}")  # Логирование ошибок
        else:
            await message.answer("🔍 Реферальный код не найден.")
    photo = FSInputFile('res/profile.jpg')
    await bot.send_photo(photo=photo, chat_id=message.from_user.id, caption="Выберите действие:",
                         reply_markup=keyboard.main_menu_markup)


# Таблица для чеков
cursor.execute('''
    CREATE TABLE IF NOT EXISTS checks (
        check_id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER,
        check_code TEXT,
        amount INTEGER,
        max_activations INTEGER,
        remaining_activations INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()
# Создаем таблицу check_claims, если она не существует
cursor.execute('''
    CREATE TABLE IF NOT EXISTS check_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
        check_id INTEGER,
        user_id INTEGER,
        claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (check_id) REFERENCES checks (check_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')


@dp.message(Command("check"))
async def create_check(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    if is_withdrawal_locked(user_id):
        await message.answer(f"[🚫] Вывод был временно заблокирован\n t.me/{config.ADMIN_USERNAME}")
        return

    if len(args) < 2 or len(args) > 3:
        await message.answer("❗ Пожалуйста, используйте формат: /check <сумма> [<@username> | <кол-во активаций>]")
        return

    try:
        amount = int(args[1])  # Проверяем сумму
    except ValueError:
        await message.answer("❌ Введите корректное числовое значение для суммы.")
        return

    recipient_username = None
    activations = None

    # Проверка, указан ли username или количество активаций
    if len(args) == 3:
        if args[2].startswith("@"):
            recipient_username = args[2]  # Указан username
            activations = 1  # Если чек для конкретного пользователя, то активаций всегда 1
        else:
            try:
                activations = int(args[2])  # Проверяем количество активаций
            except ValueError:
                await message.answer("❌ Введите корректное числовое значение для количества активаций.")
                return

    # Проверяем баланс пользователя
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    total_amount = amount * (activations if activations is not None else 1)
    if user is None or user[0] < total_amount:
        await message.answer("💔 Недостаточно средств для создания чека.")
        return

    # Списываем сумму
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (total_amount, user_id))
    conn.commit()

    # Генерируем уникальный код чека
    check_code = str(uuid.uuid4())[:8]

    # Создаем запись в таблице чеков
    cursor.execute('''
        INSERT INTO checks (creator_id, check_code, amount, max_activations, remaining_activations, recipient_username) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, check_code, amount, activations if activations else 0, activations if activations else 0,
          recipient_username))
    conn.commit()

    log_action(user_id, "Create Check", amount)

    # Создаем ссылку на чек
    check_link = f"https://t.me/{config.BOT_USERNAME}?start=check_{check_code}"

    # Создаем инлайн-кнопку
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰Активировать чек", url=check_link)]
    ])

    # Сообщение с информацией о чеке
    response_message = (
        f"🎉 <b>Чек на сумму: {amount} USDT</b> 🎉\n"
        f"🔑 <b>Активировать можно: {activations if activations else 'бесконечно'} раз(а)</b>\n"
        f"👤 <b>Получатель:</b> <code>{recipient_username if recipient_username else 'Все'}</code>\n"
        f"📅 <b>Дата создания:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"🔢 <b>Уникальный номер чека:</b> <code>{check_code}</code>\n\n"
        f"🔗 <b>Нажмите на кнопку ниже для активации:</b>\n"
    )

    await message.answer(response_message, reply_markup=inline_keyboard, parse_mode='HTML')


# Обработчик для активации чека
@dp.message(lambda message: message.text.startswith("/claim_"))
async def claim_check(message: Message):
    user_id = message.from_user.id
    check_code = message.text.split("_")[1]

    # Логика обработки активации чека
    cursor.execute(
        "SELECT check_id, creator_id, check_code, amount, max_activations, remaining_activations, recipient_username FROM checks WHERE check_code=?",
        (check_code,))
    check = cursor.fetchone()

    if not check:
        await message.answer("Чек не найден или истек срок действия.")
        return

    check_id, creator_id, check_code, amount, max_activations, remaining_activations, recipient_username = check

    # Проверяем, предназначен ли чек конкретному пользователю
    if recipient_username and recipient_username != f"@{message.from_user.username}":
        await message.answer("Этот чек предназначен для другого пользователя.")
        return

    # Проверяем, активировался ли пользователь ранее
    cursor.execute("SELECT * FROM check_claims WHERE check_id=? AND user_id=?", (check_id, user_id))
    claim = cursor.fetchone()

    if claim:
        await message.answer("Вы уже активировали этот чек.")
        return

    # Проверяем, остались ли активации
    if remaining_activations <= 0:
        await message.answer("Данный чек уже полностью использован.")
        return

    # Активируем чек, добавляем сумму пользователю
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    cursor.execute("UPDATE checks SET remaining_activations = remaining_activations - 1 WHERE check_id=?", (check_id,))
    cursor.execute("INSERT INTO check_claims (check_id, user_id) VALUES (?, ?)", (check_id, user_id))
    conn.commit()

    log_action(user_id, "Activation Check", amount)
    await message.answer(f"✅ Чек активирован!\nСумма: {amount} USDT на активацию.")

    # Уведомление владельца чека
    await bot.send_message(creator_id,
                           f"🎉 Ваш чек активирован пользователем: @{message.from_user.username}!\nСумма: {amount} USDT.")


# Обработчик нажатия кнопки "🎉 Рефералы"
@dp.message(lambda message: message.text == "🎉 Рефералы")
async def referral_info(message: Message):
    user_id = message.from_user.id
    referral_code = f"ref_{user_id}"  # Генерация уникального реферального кода для каждого пользователя

    # Проверка существования реферального кода в базе
    referral_cursor.execute("SELECT * FROM referrals WHERE referrer_user_id=?", (user_id,))
    referral_record = referral_cursor.fetchone()

    # Если кода нет, создаем новый
    if referral_record is None:
        referral_cursor.execute(
            "INSERT INTO referrals (referrer_user_id, referral_code) VALUES (?, ?)",
            (user_id, referral_code)
        )
        referral_conn.commit()

    # Получение списка ID привлеченных пользователей
    referral_cursor.execute("SELECT referred_user_id FROM referrals WHERE referrer_user_id=?", (user_id,))
    referred_users = referral_cursor.fetchall()
    referred_users_ids = [row[0] for row in referred_users if
                          row[0] is not None]  # Список ID привлечённых пользователей

    # Формирование списка имён пользователей
    referred_users_text = ""
    if referred_users_ids:
        for ref_id in referred_users_ids:
            username = await get_username_by_id(bot, ref_id)  # Получение username по ID
            referred_users_text += f"👤 @{username}\n"
        total_referrals_text = f"\nВсего рефералов: {len(referred_users_ids)}"
    else:
        referred_users_text = "Нет привлечённых пользователей."
        total_referrals_text = ""

    # Отправка пользователю информации о реферальной системе
    await message.answer(
    f"<b>🎉 С Новым Годом! 🎊</b>\n\n"
    f"<b>✨ Приглашайте друзей в казино и получайте праздничные бонусы!</b>\n"
    f"💰 За каждого нового пользователя вы получите <b>150 USDT</b>, а они — <b>100 USDT</b> на свой счет.\n\n"
    f"🔗 Ваша новогодняя реферальная ссылка:\n"
    f"<a href='https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME}?start={referral_code}'>Нажмите здесь, чтобы пригласить друзей!</a>\n\n"
    f"👥 <b>Привлечённые пользователи:</b>\n{referred_users_text}\n"
    f"<b>{total_referrals_text}</b>\n\n"
    f"🎁 Пусть этот Новый Год принесёт вам удачу и радость! 🎉"
, parse_mode='HTML')



@dp.message(Command("free"))
async def free(message: Message):
    user_id = message.from_user.id
    # Проверяем, зарегистрирован ли пользователь (добавьте свою логику регистрации)
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance, last_free_bonus, cashback) VALUES (?, ?, ?, ?)",
                   (user_id, 0, None, 0))
    conn.commit()

    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())


def main_menu_markup():
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎅 Адвент календарь", callback_data="get_free_bonus")],
        [InlineKeyboardButton(text="💵 Получить кешбек", callback_data="get_cashback")]
    ])
    return markup


@dp.callback_query(lambda c: c.data == "get_free_bonus")
async def get_free_bonus(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        last_free_bonus = user[2]  # Предполагаем, что столбец last_free_bonus - третий
        balance = user[1]  # Предполагаем, что столбец balance - второй

        if last_free_bonus is not None:
            last_free_bonus_date = datetime.strptime(last_free_bonus, '%Y-%m-%d').date()
        else:
            last_free_bonus_date = None

        current_date = datetime.today().date()

        if last_free_bonus_date is None or last_free_bonus_date < current_date:
            random_number = random.randint(1, 20)
            bonus_amount = random_number * 10
            new_balance = balance + bonus_amount
            current_date = datetime.today().date()

            cursor.execute("UPDATE users SET balance = ?, last_free_bonus = ? WHERE user_id = ?",
                           (new_balance, current_date, user_id))
            conn.commit()

            await callback.message.answer(
                f"🎉 Вы получили подарок из каледаря в размере {bonus_amount} $! Ваш новый баланс: {new_balance} $.")
        else:
            await callback.message.edit_text("🚫 Вы уже получили подарок из каледаря сегодня. Попробуйте снова завтра!")
    else:
        await callback.message.edit_text("🚫 Вы не зарегистрированы. Используйте /start для регистрации.")


@dp.callback_query(lambda c: c.data == "get_cashback")
async def get_cashback(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        cashback = user[3]  # Предполагаем, что столбец cashback - четвёртый

        if cashback > 1:
            new_balance = user[1] + cashback  # Обновляем баланс
            cursor.execute("UPDATE users SET balance = ?, cashback = ? WHERE user_id = ?",
                           (new_balance, 0, user_id))  # Обнуляем кешбек
            conn.commit()

            await callback.message.answer(
                f"💵 Вы получили кешбек в размере {cashback} $! Ваш новый баланс: {new_balance} $.\n"
                f"💵 Ваш кешбек обнулён.")
        else:
            await callback.message.answer(f"🚫 У вас недостаточно кешбека для получения. Текущий кешбек: {cashback} $.")
    else:
        await callback.message.answer("🚫 Вы не зарегистрированы. Используйте /start для регистрации.")


def strip_html(text):
    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)


def get_user_balance_and_prefix(user_id):
    with sqlite3.connect("casino_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, prefix_id FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

    if result:
        balance, prefix_id = result
        # Проверяем, является ли prefix_id пустой строкой
        if prefix_id == '':
            prefix_id = None
        return balance, int(prefix_id) if prefix_id is not None else None  # Преобразуем в int, если не None
    return 0, None


# Обновление баланса и префикса пользователя
def update_user_balance_and_prefix(user_id, balance, prefix_id):
    with sqlite3.connect("casino_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET balance = ?, prefix_id = ? WHERE user_id = ?", (balance, prefix_id, user_id)
        )
        conn.commit()


@dp.message(lambda message: message.text == "👻Префиксы")
async def show_prefix_menu(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰Магазин префиксов", callback_data="shop_prefixed")],
        [InlineKeyboardButton(text="🎈Сундук с префиксами", callback_data="prefix_box")],
        [InlineKeyboardButton(text="🎗️Изменить имя", callback_data="rename_me")]
    ])
    await message.answer("Вы попали в магазин префиксов! Выберите действие: ", reply_markup=markup)


@dp.callback_query(lambda c: c.data == "prefix_box")
async def show_prefix_box(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Дешёвый сундук", callback_data="last_box")],
        [InlineKeyboardButton(text="💎 Дорогой сундук", callback_data="eba_box")]
    ])
    text = (
        "🎈 <b>Выбор сундука с префиксами</b> 🎈\n\n"
        "💬 Хочешь выделиться среди игроков? Открой один из наших сундуков с уникальными префиксами! "
        "В каждом сундуке – шанс получить что-то действительно особенное.\n\n"
        "<b>Выбери свой сундук:</b>\n\n"
        "💵 <b>Дешёвый сундук</b> – <i>500💸</i>\n"
        "<code>Шанс на более доступные префиксы, но может выпасть и что-то ценное!</code>\n\n"
        "💎 <b>Дорогой сундук</b> – <i>2500💸</i>\n"
        "<code>Повышенный шанс на дорогие и редкие префиксы! Для тех, кто ищет лучшие награды.</code>\n\n"
        "🎲 <i>Почувствуй азарт и выбери сундук, чтобы узнать, что выпадет именно тебе!</i>"
    )
    await callback.message.answer(text, reply_markup=markup, parse_mode='HTML')
    await callback.message.delete()


cheap_prefixes = [0, 1, 4, 6, 8]  # Дешёвые префиксы
expensive_prefixes = [2, 3, 7, 9, 5]  # Дорогие префиксы

# Стоимость сундуков
cheap_box_price = 500
expensive_box_price = 2500


# Функция для получения соединения с базой данных
def get_db():
    conn = sqlite3.connect("casino_bot.db")
    return conn


# Функция для обновления баланса и префикса в базе данных
def update_user(user_id, new_balance, prefix_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ?, prefix_id = ? WHERE user_id = ?", (new_balance, prefix_id, user_id))
    conn.commit()
    conn.close()


# Дешёвый сундук
@dp.callback_query(lambda c: c.data == "last_box")
async def show_last(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Получаем текущий баланс пользователя
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()

    # Проверка баланса
    if balance < cheap_box_price:
        await callback.message.answer("❌ Недостаточно средств для покупки дешёвого сундука!")
        return

    # Списывание средств и выбор префикса
    new_balance = balance - cheap_box_price
    prefix_id = random.choice(cheap_prefixes)
    update_user(user_id, new_balance, prefix_id)

    # Сообщение о результате
    prefix_info = prefixes[prefix_id]
    text = (
        f"💵 <b>Дешёвый сундук открыт!</b>\n\n"
        f"🎉 Поздравляем! Тебе выпал префикс: {prefix_info['name']}!\n"
        f"<blockquote>{prefix_info['description']}</blockquote>\n\n"
        f"💰 <b>Ваш новый баланс:</b> {round(new_balance)}💸"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.message.delete()

    # Отправка сообщения в канал
    channel_message = (
        f"🎈 Игрок @{callback.from_user.username} открыл дешёвый сундук и выиграл префикс {prefix_info['name']}! 🎉\n"
        f"<blockquote>{prefix_info['description']}</blockquote>\n\n"
        f"💸 <b>Стоимость префикса:</b> {prefix_info['price']}💸"
    )
    await bot.send_message(chat_id=config.win_id, text=channel_message, parse_mode="HTML")


# Дорогой сундук
@dp.callback_query(lambda c: c.data == "eba_box")
async def show_eba(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Получаем текущий баланс пользователя
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()

    # Проверка баланса
    if balance < expensive_box_price:
        await callback.message.answer("❌ Недостаточно средств для покупки дорогого сундука!")
        return

    # Списывание средств и выбор префикса
    new_balance = balance - expensive_box_price
    prefix_id = random.choice(expensive_prefixes)
    update_user(user_id, new_balance, prefix_id)

    # Сообщение о результате
    prefix_info = prefixes[prefix_id]
    text = (
        f"💎 <b>Дорогой сундук открыт!</b>\n\n"
        f"🎉 Поздравляем! Тебе выпал редкий префикс: {prefix_info['name']}!\n"
        f"<blockquote>{prefix_info['description']}</blockquote>\n\n"
        f"💰 <b>Ваш новый баланс:</b> {round(new_balance)}$ 💸"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.message.delete()

    # Отправка сообщения в канал
    channel_message = (
        f"🎈 Игрок @{callback.from_user.username} открыл дорогой сундук и выиграл редкий префикс {prefix_info['name']}! 🎉\n"
        f"<blockquote>{prefix_info['description']}</blockquote>\n\n"
        f"💸 <b>Стоимость префикса:</b> {prefix_info['price']} $💸"
    )
    await bot.send_message(chat_id=config.win_id, text=channel_message, parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "shop_prefixed")
async def shop_prefixed(callback: types.CallbackQuery):
    await send_prefix_menu(callback.message.chat.id, 0)  # Начинаем с первого префикса
    await callback.message.delete()


# Функция отображения меню с префиксами
async def send_prefix_menu(chat_id, prefix_index):
    builder = InlineKeyboardBuilder()

    # Получаем текущий префикс и формируем текст сообщения
    current_prefix = prefixes[prefix_index]
    message_text = (
        f"<b>Префикс для покупки:</b> {current_prefix['name']}\n"
        f"<b>Описание:</b> <blockquote>{current_prefix['description']}</blockquote>\n"
        f"💰 Цена: {current_prefix['price']} 💰\n\n"
        f"⚠️ Покупая новый префикс, ваш старый префикс будет удален, и вы получите 50% от его стоимости.\n\n"
    )

    # Добавляем кнопки "Назад", "Вперед" и "Купить"
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"prefix:prev:{prefix_index}"),
        InlineKeyboardButton(text="Купить", callback_data=f"prefix:select:{prefix_index}"),
        InlineKeyboardButton(text="➡️", callback_data=f"prefix:next:{prefix_index}")
    )

    # Отправляем или редактируем сообщение с меню
    await bot.send_message(chat_id, message_text, reply_markup=builder.as_markup(), parse_mode="HTML")


# Обработчик callback'ов для перелистывания и покупки префиксов
@dp.callback_query(lambda call: call.data.startswith("prefix:"))
async def prefix_callback_handler(callback_query: CallbackQuery):
    global new_index
    data = callback_query.data.split(":")
    action = data[1]
    current_index = int(data[2])
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Без ника"
    user_balance, current_prefix_id = get_user_balance_and_prefix(user_id)

    # Если у пользователя нет текущего префикса
    if current_prefix_id is None:
        current_prefix_id = -1  # Обозначаем, что префикс не установлен
        current_prefix_name = None
    else:
        current_prefix_name = prefixes[current_prefix_id]["name"] if current_prefix_id < len(prefixes) else None

    if action == "prev":
        new_index = (current_index - 1) % len(prefixes)
    elif action == "next":
        new_index = (current_index + 1) % len(prefixes)
    elif action == "select":
        selected_prefix = prefixes[current_index]

        # Если у пользователя уже есть префикс, вернем ему 50% стоимости
        refund = 0
        if current_prefix_id >= 0:  # Проверяем, установлен ли префикс
            for prefix in prefixes:
                if prefix["name"] == current_prefix_name:  # Сравниваем без символа
                    refund = prefix["price"] // 2
                    user_balance += refund
                    break

        # Проверка баланса
        if user_balance >= selected_prefix["price"]:
            new_balance = user_balance - selected_prefix["price"]
            update_user(user_id, new_balance, current_index)  # Сохраняем индекс префикса

            # Сообщение о покупке префикса
            await callback_query.message.edit_text(
                f"🎉 Вы приобрели префикс: {selected_prefix['name']}\n\n"
                f"💰 <b>Потрачено:</b> {selected_prefix['price']} 💰\n"
                f"💸 <b>Вернулось за прошлый префикс:</b> {refund} 💰\n"
                f"💵 <b>Новый баланс:</b> {new_balance:.2f}$ 💰\n"

                f"<b>Описание префикса:</b>\n<blockquote>{selected_prefix['description']}</blockquote>",
                parse_mode="HTML"
            )

            # Отправляем уведомление админам
            await notify_admins(
                f"🛒 <b>Покупка префикса</b>\n"
                f"👤 <b>Пользователь:</b> @{username} (ID: {user_id})\n"
                f"🔹 <b>Куплено:</b> {selected_prefix['name']} за {selected_prefix['price']} 💰\n"
                f"🔹 <b>Прошлый префикс:</b> {current_prefix_name or 'Не было'}\n"
                f"🔹 <b>Компенсация за старый префикс:</b> {refund} 💰"
            )
        else:
            await callback_query.message.answer("❌ Недостаточно средств для покупки этого префикса.", parse_mode="HTML")
        await callback_query.answer()
        return

    # Обновляем меню с новым префиксом
    await callback_query.message.edit_text(
        f"<b>Префикс для покупки:</b> {prefixes[new_index]['name']}\n"
        f"<b>Описание:</b> <blockquote>{prefixes[new_index]['description']}</blockquote>\n"
        f"💰 Цена: {prefixes[new_index]['price']} 💰\n\n"
        f"⚠️ Покупая новый префикс, ваш старый префикс будет удален, и вы получите 50% от его стоимости.\n\n",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️", callback_data=f"prefix:prev:{new_index}"),
            InlineKeyboardButton(text="Купить", callback_data=f"prefix:select:{new_index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"prefix:next:{new_index}")
        ).as_markup(),
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.message(Command("balance"))
async def send_balance(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance = user[0]
        balance = "{:.2f}".format(balance)
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰Пополнить баланс", callback_data="add_balance")]
        ])
        await message.answer(f"💰 Ваш баланс: {balance} USDT", reply_markup=markup)
    else:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")


@dp.message(lambda message: message.text == "🎉Рефералы")
async def send_referral_info(message: Message):
    user_id = message.from_user.id

    # Получаем реферальную ссылку
    referral_link = generate_referral_link(user_id)

    # Информация о правилах и призах
    referral_info = (
        "🎉 Программа рефералов\n\n"
        "Пригласите своих друзей и получите вознаграждение! Вот как это работает:\n\n"
        "1. Как пригласить друзей: Отправьте своим друзьям вашу уникальную реферальную ссылку.\n"
        "2. Что вы получаете: Вы получите 100 USDT за каждого приглашенного друга, который зарегистрируется и начнет использовать наше казино.\n\n"
        f"🌟 Ваша уникальная реферальная ссылка: {referral_link}\n"
        f"РЕФЕРАЛКА ВРЕМЕННО НЕ РАБОТАЕТ!!!!!!!!!!!!!!!!!!!!!!!!"
    )

    await message.answer(referral_info)


@dp.message(lambda message: message.text in ["💰 Баланс", "🎮 Играть", "💳 Пополнить", "🏦 Вывод", "🎅 Адвент календарь"])
async def handle_buttons(message: Message):
    if message.text == "💰 Баланс":
        await send_balance(message)
    elif message.text == "🎮 Играть":
        await play_game(message)
    elif message.text == "💳 Пополнить":
        await deposit(message)
    elif message.text == "🏦 Вывод":
        await withdraw(message)
    elif message.text == "🎅 Адвент календарь":
        await free(message)


# Команда /addbalance для выбора суммы пополнения
@dp.message(Command("deposit"))
async def deposit(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 $1", callback_data="deposit_1")],
            [InlineKeyboardButton(text="💰 $10", callback_data="deposit_10")],
            [InlineKeyboardButton(text="💸 $100", callback_data="deposit_100")],
            [InlineKeyboardButton(text="💵 $500", callback_data="deposit_500")],
            [InlineKeyboardButton(text="💰 $1000", callback_data="deposit_1000")],
            [InlineKeyboardButton(text="💎 $5000", callback_data="deposit_5000")],
            [InlineKeyboardButton(text="💎 $10000", callback_data="deposit_10000")]

        ])
        await message.answer("💳 Выберите сумму для пополнения:", reply_markup=markup)
    else:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")


@dp.callback_query(lambda c: c.data == "add_balance")
async def add_balance(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id  # Исправлено на callback_query
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💵 $1", callback_data="deposit_1")],
            [types.InlineKeyboardButton(text="💰 $10", callback_data="deposit_10")],
            [types.InlineKeyboardButton(text="💸 $100", callback_data="deposit_100")],
            [types.InlineKeyboardButton(text="💵 $500", callback_data="deposit_500")],
            [types.InlineKeyboardButton(text="💰 $1000", callback_data="deposit_1000")],
            [types.InlineKeyboardButton(text="💎 $5000", callback_data="deposit_5000")],
            [types.InlineKeyboardButton(text="💎 $10000", callback_data="deposit_10000")]
        ])
        await callback_query.message.edit_text("💳 Выберите сумму для пополнения:", reply_markup=markup)
    else:
        await callback_query.message.edit_text("Вы не зарегистрированы. Используйте /start для регистрации.")


@dp.callback_query(lambda c: c.data and c.data.startswith("deposit_"))
async def process_deposit(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    amount = int(callback_query.data.split("_")[1])  # Получаем сумму из callback_data
    invoice = await cryptopay.create_invoice(asset='USDT', amount=amount, description=f'{callback_query.from_user.id}')

    # Кнопки для оплаты
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить через мини-приложение", url=invoice.mini_app_invoice_url)],
        [InlineKeyboardButton(text="Оплатить через бота", url=invoice.bot_invoice_url)]
    ])
    await bot.send_message(user_id, f"Переведите {amount} USDT для пополнения баланса.", reply_markup=markup)
    await callback_query.answer()

    # Начинаем проверку платежа

    while True:
        invoices = await cryptopay.get_invoices()
        for inv in invoices:
            invoice_id = invoices[0].invoice_id
            status = invoices[0].status
            amounts = invoices[0].amount
            user_id_from_comment = invoices[0].description  # Предполагаем, что ID пользователя передается в комментарии

            # Проверяем, оплачен ли счет и не был ли он уже обработан
            # Предполагаем, что processed_invoices - это множество для хранения обработанных счетов
            if status == 'paid' and invoice_id not in processed_invoices:
                # Проверяем, совпадает ли ID пользователя в комментарии с ожидаемым

                # Обновляем баланс и уведомляем пользователя
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amounts, user_id))
                conn.commit()
                log_action(user_id, "Deposit", amounts)

                # Зафиксируем, что счет обработан
                processed_invoices.append(invoice_id)
                image = Image.open("res/paid.jpg")
                draw = ImageDraw.Draw(image)

                # Устанавливаем шрифт и размер
                font = ImageFont.truetype("res/Cruinn.ttf", size=130)

                # Устанавливаем текст и его позицию
                text = f"+{amounts} USDT"
                position = (300, 450)  # Попробуйте изменить на (50, 50) или другую позицию

                # Устанавливаем цвет текста
                text_color = (255, 255, 255)  # Белый цвет

                # Добавляем текст на изображение
                draw.text(position, text, fill=text_color, font=font)

                # Сохраняем измененное изображение во временный файл
                temp_image_path = "res/temp_image.jpg"
                image.save(temp_image_path)

                # Создаем объект FSInputFile с измененным изображением
                photos = FSInputFile(temp_image_path)
                cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id_from_comment,))
                new_balance = cursor.fetchone()[0]
                new_balance = "{:.2f}".format(new_balance)
                await bot.send_photo(user_id_from_comment,
                                     caption=f'<blockquote> ✅ Ваш баланс был пополнен на {amounts} USDT. Ваш текущий баланс: {new_balance} USDT.</blockquote>',
                                     photo=photos,
                                     parse_mode="html")

                # Уведомляем администраторов
                username = await get_username_by_id(bot, user_id)
                await notify_admins(f"💳 Пополнение баланса:\n\nПользователь ID: {user_id}\n"
                                    f"Пользователь: @{username}\n"
                                    f"Сумма: {amounts} USDT")

                break  # Выходим из цикла после обработки платежа


        else:
            await asyncio.sleep(10)  # Ждем 10 секунд перед следующей проверкой
            continue
        break  # Выход из внешнего цикла, если найден и обработан оплаченный счет


user_game_status = {}


@dp.message(Command("play"))
async def play_game(message: types.Message, user_id: int = None):
    if user_id is None:
        user_id = message.from_user.id

    if is_user_locked(user_id):
        await message.answer(f"Вы были заблокированы t.me/{config.ADMIN_USERNAME}")
        return

    chat_member = await bot.get_chat_member(chat_id=config.win_id, user_id=user_id)
    chat_member2 = await bot.get_chat_member(chat_id=config.Sub_Id, user_id=user_id)

    if chat_member.status not in ['member', 'administrator', 'creator'] or chat_member2.status not in ['member',
                                                                                                       'administrator',
                                                                                                       'creator']:
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰{config.win_Name}", url=f"{config.win_Link}")],
            [InlineKeyboardButton(text=f"{config.Sub_Name}", url=f"{config.Sub_Link}")]
        ])

        await message.answer("Чтобы продолжить, пожалуйста, подпишитесь на наш канал:", reply_markup=inline_keyboard)

    # Проверяем, играет ли пользователь
    if user_game_status.get(user_id, {}).get("is_playing", False):
        await message.answer("🚫 Вы уже играете. Подождите, пока текущая игра завершится.")
        return

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user and user[0] >= 1:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Чет/Нечет", callback_data="mode_even_odd")],
            [InlineKeyboardButton(text="🔼 Больше/Меньше", callback_data="mode_higher_lower")],
            [InlineKeyboardButton(text="🛍️ Пакеты", callback_data="mode_boxes")],
            [InlineKeyboardButton(text="🎰Слоты", callback_data="mode_slots")]
        ])
        await message.answer("🕹️ Объяснение игры - /help \nВыберите режим игры:", reply_markup=markup)
    else:
        await message.answer("🚫 На вашем балансе недостаточно средств для игры. Пополните баланс с помощью /deposit.")


@dp.callback_query(lambda c: c.data.startswith("mode_"))
async def choose_game_mode(callback_query: CallbackQuery):
    await callback_query.answer()

    user_id = callback_query.from_user.id
    game_mode = callback_query.data.split("_")[1]

    # Проверяем, играет ли пользователь
    if user_game_status.get(user_id, {}).get("is_playing", False):
        await callback_query.message.answer("🚫 Вы уже играете. Подождите, пока текущая игра завершится.")
        return

    user_game_status[user_id] = {"is_playing": True}  # Устанавливаем статус, когда пользователь выбирает режим

    if game_mode == "even":
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Чет", callback_data="bet_even")],
            [InlineKeyboardButton(text="🎲 Нечет", callback_data="bet_odd")]
        ])
        await callback_query.message.edit_text("Выберите исход: Чет или Нечет.", reply_markup=markup)
    elif game_mode == "higher":
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔼 Больше", callback_data="bet_higher")],
            [InlineKeyboardButton(text="🔽 Меньше", callback_data="bet_lower")]
        ])
        await callback_query.message.edit_text("Выберите исход: Больше или Меньше.", reply_markup=markup)
    elif game_mode == "boxes":
        await callback_query.message.edit_text("Вы выбрали режим: 🛍️ Пакеты")
        time.sleep(1)

        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()

        if user:
            balance = user[0]

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 1 $", callback_data=f"stake_1_{game_mode}")],
            [InlineKeyboardButton(text="💰 10 $", callback_data=f"stake_10_{game_mode}")],
            [InlineKeyboardButton(text="💸 100 $", callback_data=f"stake_100_{game_mode}")],
            [InlineKeyboardButton(text="🤑 500 $", callback_data=f"stake_500_{game_mode}")],
            [InlineKeyboardButton(text="💴 1000 $", callback_data=f"stake_1000_{game_mode}")],
            [InlineKeyboardButton(text="💰 5000 $", callback_data=f"stake_5000_{game_mode}")],
            [InlineKeyboardButton(text=f"🤑 {balance} $ (All) ", callback_data=f"stake_{int(balance)}_{game_mode}")]
        ])
        await callback_query.message.edit_text("Выберите сумму ставки:", reply_markup=markup)

    elif game_mode == "slots":
        message = """
        <b>Правила игры "Слоты":</b>\n
        В игре есть 4 возможные комбинации:\n
           - <b>Три семёрки (777)</b> — выигрыш 10X вашей ставки!\n
           - <b>Три винограда (🍇🍇🍇)</b>, <b>три лимона (🍋🍋🍋)</b>, или <b>три BAR (BAR BAR BAR)</b> — выигрыш 4X вашей ставки!\n
        """

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍇 Начать игру", callback_data="bet_slots")]
        ])

        await callback_query.message.edit_text(text=message, reply_markup=markup, parse_mode="HTML")






    else:
        await callback_query.message.edit_text("Неверный режим игры.")


@dp.callback_query(lambda c: c.data.startswith("bet_"))
async def choose_bet(callback_query: CallbackQuery):
    global balance
    await callback_query.answer()

    user_id = callback_query.from_user.id
    bet_choice = callback_query.data.split("_")[1]
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user_balance = cursor.fetchone()
    if user_balance:
        balance = user_balance[0]
        balance_float = float(balance)  # Преобразуем в float
        balance = int(balance_float)  # Убираем дробную часть
    # Сохранение выбранного исхода
    user_game_status[user_id]["bet_choice"] = bet_choice  # Сохраняем выбор ставки

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 1 $", callback_data=f"stake_1_{bet_choice}")],
        [InlineKeyboardButton(text="💰 10 $", callback_data=f"stake_10_{bet_choice}")],
        [InlineKeyboardButton(text="💸 100 $", callback_data=f"stake_100_{bet_choice}")],
        [InlineKeyboardButton(text="🤑 500 $", callback_data=f"stake_500_{bet_choice}")],
        [InlineKeyboardButton(text="💴 1000 $", callback_data=f"stake_1000_{bet_choice}")],
        [InlineKeyboardButton(text="💰 5000 $", callback_data=f"stake_5000_{bet_choice}")],
        [InlineKeyboardButton(text=f"🤑 {balance} $ (All) ", callback_data=f"stake_{int(balance)}_{bet_choice}")]
    ])
    await callback_query.message.edit_text("Выберите сумму ставки:", reply_markup=markup)


# Глобальная переменная

message_id_save = int()


@dp.callback_query(lambda c: c.data.startswith("stake_"))
async def choose_stake(callback_query: CallbackQuery):
    await callback_query.answer()
    global message_id_save
    global saved_message_id

    user_id = callback_query.from_user.id
    stake_data = callback_query.data.split("_")
    stake_amount = int(stake_data[1])
    bet_choice = stake_data[2]  # Получаем выбор ставки (чет, нечет, больше, меньше)

    user_id = callback_query.from_user.id
    stake_amount = int(callback_query.data.split("_")[1])

    cursor.execute("SELECT cashback FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        current_cashback = user[0]
        new_cashback = current_cashback + (stake_amount * 0.001)  # 0.1% кешбека
        cursor.execute("UPDATE users SET cashback = ? WHERE user_id=?", (new_cashback, user_id))
        conn.commit()

    if bet_choice == "slots":
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰Играть в слоты", callback_data=f"slotplay_{stake_amount}_{bet_choice}")]
        ])

        edited_message = await callback_query.message.edit_text(
            f"💰 Вы выбрали ставку: {stake_amount} $.\n"
            f"Нажмите кнопку ниже, чтобы играть в слоты и узнать итог!",
            reply_markup=markup  # Кнопки для броска кубика
        )
        message_id_save = edited_message.message_id


    if bet_choice == "boxes":
        markup = InlineKeyboardMarkup(inline_keyboard=
        [
            [InlineKeyboardButton(text="🛍", callback_data=f"box_1_{stake_amount}"),
             InlineKeyboardButton(text="🛍", callback_data=f"box_2_{stake_amount}"),
             InlineKeyboardButton(text="🛍", callback_data=f"box_3_{stake_amount}")]
        ]
        )
        await callback_query.message.edit_text("Выберите пакетик:", reply_markup=markup)

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user and user[0] >= stake_amount:
        if bet_choice != 'slots':
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Кинуть кубик", callback_data=f"play_{stake_amount}_{bet_choice}")]
            ])
            # Отправляем сообщение с ставкой и исходом
            user_id = callback_query.from_user.id  # Получаем ID пользователя
            bet_choice = user_game_status[user_id]["bet_choice"]  # Извлекаем сохраненный исход

            # Преобразуем значения исхода в более понятные:
            if bet_choice == "even":
                bet_choice_text = "Четное"
            elif bet_choice == "odd":
                bet_choice_text = "Нечетное"
            elif bet_choice == "higher":
                bet_choice_text = "Больше"
            elif bet_choice == "lower":
                bet_choice_text = "Меньше"
            else:
                bet_choice_text = bet_choice  # На случай других вариантов

            # Редактируем текст сообщения:
            edited_message = await callback_query.message.edit_text(
                f"💰 Вы выбрали ставку: {stake_amount} $.\n"
                f"🎲 Исход: {bet_choice_text}.\n"  # Человеко-читаемый исход
                f"Нажмите кнопку ниже, чтобы бросить кубик и узнать итог!",
                reply_markup=markup  # Кнопки для броска кубика
            )
            message_id_save = edited_message.message_id

    else:
        await callback_query.message.edit_text(
            text="🚫 На вашем балансе недостаточно средств для этой игры. Пополните баланс с помощью /deposit.")
        user_game_status[user_id]["is_playing"] = False  # Сбрасываем состояние игры


@dp.callback_query(lambda c: c.data.startswith("box_"))
async def choose_box(callback_query: CallbackQuery):
    await callback_query.answer()

    user_id = callback_query.from_user.id
    box_data = callback_query.data.split("_")
    chosen_box = int(box_data[1])
    stake_amount = int(box_data[2])

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance = user[0]
        if balance >= stake_amount:
            try:
                prize_box = random.randint(1, 3)

                if chosen_box == prize_box:

                    win_amount = round(stake_amount * config.box_cof, 1)
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                    result_message = f"🎉 Вы выбрали пакет {chosen_box} и нашли приз! Вы выиграли {win_amount:.1f} USDT!"
                    user_name = callback_query.from_user.username
                    await notify_win(user_name, win_amount, stake_amount, user_id, 'Пакеты 🛍️', is_win=True)
                else:
                    win_amount = round(stake_amount * config.box_cof, 1)
                    user_name = callback_query.from_user.username

                    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (stake_amount, user_id))
                    result_message = f"😔 Вы выбрали пакет {chosen_box}, но не нашли приз. Вы проиграли {stake_amount:.1f} USDT."
                    await notify_win(user_name, win_amount, stake_amount, user_id, 'Пакеты🛍️', is_win=False)

                conn.commit()
                updated_balance = cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()[0]
                updated_balance = round(updated_balance, 1)

                inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎲Играть снова", callback_data="played_game")]
                ])

                await callback_query.message.edit_text(
                    f"{result_message}\n💵 Ваш текущий баланс: {updated_balance} $.")
                user_game_status[user_id]["is_playing"] = False

            except Exception as e:
                await callback_query.message.answer(f"⚠️ Ошибка при обновлении баланса: {e}")
                conn.rollback()
        else:
            await callback_query.message.edit_text(
                "🚫 На вашем балансе недостаточно средств для этой игры. Пополните баланс с помощью /deposit.")

def get_combo_text(dice_value: int):

    #           0       1         2        3
    values = ["BAR", "виноград", "лимон", "семь"]

    dice_value -= 1
    result = []
    for _ in range(3):
        result.append(values[dice_value % 4])
        dice_value //= 4
    return result

@dp.callback_query(lambda c: c.data.startswith("slotplay_"))
async def slotplay(callback_query: CallbackQuery):
    global result_message, photo
    user_id = callback_query.from_user.id
    play_data = callback_query.data.split("_")
    stake_amount = int(play_data[1])
    bet_choice = play_data[2]  # Получаем выбор ставки (чет, нечет, больше, меньше)

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user and user[0] >= stake_amount:
        a = 1
        if a == 1:
            global message_id_save
            dice_message = await callback_query.message.answer_dice(emoji="🎰")
            await callback_query.bot.delete_message(callback_query.message.chat.id, message_id_save)
            resulted = get_combo_text(dice_message.dice.value)
            print(resulted)

            if resulted == ['виноград', 'виноград', 'виноград'] or resulted == ['BAR', 'BAR', 'BAR'] or resulted == ['лимон', 'лимон', 'лимон']:

                win_amount = round(stake_amount * config.coof3, 1)
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                time.sleep(1)
                #photo = FSInputFile('res/chet.jpg')
                result_message = f"🎉 Вам выпало 3 в ряд!. Вы выиграли {win_amount:.1f} USDT!"
                user_name = callback_query.from_user.username
                await notify_win(callback_query.from_user.username, win_amount, stake_amount, user_id, '🎰3 в ряд!',
                                is_win=True)

            elif resulted == ['семь', 'семь', 'семь']:
                win_amount = round(stake_amount * config.coof7, 1)
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                time.sleep(1)
                # photo = FSInputFile('res/chet.jpg')
                result_message = f"🎉 Вам выпало 777 в ряд!. Вы выиграли {win_amount:.1f} USDT!"
                user_name = callback_query.from_user.username
                await notify_win(callback_query.from_user.username, win_amount, stake_amount, user_id, '🎰777 в ряд!',
                                is_win=True)

            else:
                loss_amount = round(stake_amount, 1)
                cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (loss_amount, user_id))
                time.sleep(1)
                result_message = f"😔 Вам не выпала выигрышная комбинация. Вы проиграли {loss_amount:.1f} USDT."
                #photo = FSInputFile('res/nechet.jpg')
                await notify_win(callback_query.from_user.username, loss_amount, stake_amount, user_id,
                                'Игровые автоматы 🎰', is_win=False)

            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲Играть снова", callback_data="played_game")]
            ])

            #photo_message = await bot.send_photo(user_id, caption=result_message, photo=photo,
                          #                       reply_markup=inline_keyboard)

            message_texted = await  bot.send_message(chat_id=user_id, text=result_message, reply_markup=inline_keyboard)
            message_id_save = message_texted.message_id

            # Сбрасываем состояние после игры
            user_game_status[user_id]["is_playing"] = False






@dp.callback_query(lambda c: c.data.startswith("play_"))
async def play_dice_game(callback_query: CallbackQuery):
    global result_message, photo
    user_id = callback_query.from_user.id
    play_data = callback_query.data.split("_")
    stake_amount = int(play_data[1])
    bet_choice = play_data[2]  # Получаем выбор ставки (чет, нечет, больше, меньше)

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user and user[0] >= stake_amount:
        try:
            global message_id_save
            dice_message = await callback_query.message.answer_dice(emoji="🎲")
            await callback_query.bot.delete_message(callback_query.message.chat.id, message_id_save)
            dice_value = dice_message.dice.value

            # Логика выигрыша/проигрыша
            if bet_choice == "even":
                if dice_value % 2 == 0:
                    win_amount = round(stake_amount * config.coefficient, 1)
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                    time.sleep(3)
                    photo = FSInputFile('res/chet.jpg')
                    result_message = f"🎉 Вам выпало {dice_value}. Вы выиграли {win_amount:.1f} USDT!"
                    user_name = callback_query.from_user.username
                    await notify_win(callback_query.from_user.username, win_amount, stake_amount, user_id, 'Чет/Нечет🎲',
                                     is_win=True)
                else:
                    loss_amount = round(stake_amount, 1)
                    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (loss_amount, user_id))
                    time.sleep(3)
                    result_message = f"😔 Вам выпало {dice_value}. Вы проиграли {loss_amount:.1f} USDT."
                    photo = FSInputFile('res/nechet.jpg')
                    await notify_win(callback_query.from_user.username, loss_amount, stake_amount, user_id,
                                     'Чет/Нечет🎲', is_win=False)

            elif bet_choice == "odd":
                if dice_value % 2 != 0:
                    win_amount = round(stake_amount * config.coefficient, 1)
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                    time.sleep(3)
                    result_message = f"🎉 Вам выпало {dice_value}. Вы выиграли {win_amount:.1f} USDT!"
                    photo = FSInputFile('res/nechet.jpg')
                    user_name = callback_query.from_user.username
                    await notify_win(callback_query.from_user.username, win_amount, stake_amount, user_id, 'Чет/Нечет🎲',
                                     is_win=True)
                else:
                    loss_amount = round(stake_amount, 1)
                    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (loss_amount, user_id))
                    time.sleep(3)
                    result_message = f"😔 Вам выпало {dice_value}. Вы проиграли {loss_amount:.1f} USDT."
                    photo = FSInputFile('res/chet.jpg')
                    await notify_win(callback_query.from_user.username, loss_amount, stake_amount, user_id,
                                     'Чет/Нечет🎲', is_win=False)

            elif bet_choice == "higher":
                if dice_value >= 4:
                    win_amount = round(stake_amount * config.coefficient, 1)
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                    time.sleep(3)
                    result_message = f"🎉 Вам выпало {dice_value}. Вы выиграли {win_amount:.1f} USDT!"
                    photo = FSInputFile('res/bolshe.jpg')
                    user_name = callback_query.from_user.username
                    await notify_win(callback_query.from_user.username, win_amount, stake_amount, user_id,
                                     'Больше/Меньше🎲', is_win=True)
                else:
                    loss_amount = round(stake_amount, 1)
                    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (loss_amount, user_id))
                    time.sleep(3)
                    result_message = f"😔 Вам выпало {dice_value}. Вы проиграли {loss_amount:.1f} USDT."
                    photo = FSInputFile('res/menche.jpg')
                    await notify_win(callback_query.from_user.username, loss_amount, stake_amount, user_id,
                                     'Больше/Меньше🎲', is_win=False)

            elif bet_choice == "lower":
                if dice_value < 4:
                    win_amount = round(stake_amount * config.coefficient, 1)
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
                    time.sleep(3)
                    result_message = f"🎉 Вам выпало {dice_value}. Вы выиграли {win_amount:.1f} USDT!"
                    photo = FSInputFile('res/menche.jpg')
                    user_name = callback_query.from_user.username
                    await notify_win(callback_query.from_user.username, win_amount, stake_amount, user_id,
                                     'Больше/Меньше🎲', is_win=True)
                else:
                    loss_amount = round(stake_amount, 1)
                    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (loss_amount, user_id))
                    time.sleep(3)
                    result_message = f"😔 Вам выпало {dice_value}. Вы проиграли {loss_amount:.1f} USDT."
                    photo = FSInputFile('res/bolshe.jpg')
                    await notify_win(callback_query.from_user.username, loss_amount, stake_amount, user_id,
                                     'Больше/Меньше🎲', is_win=False)

            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲Играть снова", callback_data="played_game")]
            ])

            photo_message = await bot.send_photo(user_id, caption=result_message, photo=photo,
                                                 reply_markup=inline_keyboard)
            message_id_save = photo_message.message_id

            # Сбрасываем состояние после игры
            user_game_status[user_id]["is_playing"] = False
        except Exception as e:
            print(f"Ошибка: {e}")
            await callback_query.message.answer("🚫 Произошла ошибка при игре. Пожалуйста, попробуйте снова.")
            user_game_status[user_id]["is_playing"] = False  # Сбрасываем состояние в случае ошибки
    else:
        await callback_query.message.answer("🚫 У вас недостаточно средств для ставки.")


user_cooldowns = {}

COOLDOWN_TIME = 30  # Время кд в секундах


@dp.callback_query(lambda call: call.data == "played_game")
async def handle_play_game_callback(call: types.CallbackQuery):
    await call.bot.delete_message(call.message.chat.id, message_id_save)
    user_id = call.from_user.id
    await call.answer("Удачи!")  # Уведомляем пользователя о нажатии
    await play_game(call.message, user_id)  # Вызываем вашу функцию


@dp.message(Command("outbalance"))
async def withdraw(message: types.Message):
    user_id = message.from_user.id
    if is_withdrawal_locked(user_id):
        await message.answer(f"[🚫] Вывод был временно заблокирован\n t.me/{config.ADMIN_USERNAME}")
        return

    if is_user_locked(user_id):
        await message.answer(f"Вы были заблокированы t.me/{config.ADMIN_USERNAME}")
        return

    # Проверка, если пользователь уже успешно выводил средства недавно
    if user_id in user_cooldowns:
        last_withdraw_time = user_cooldowns[user_id]
        time_diff = datetime.now() - last_withdraw_time
        if time_diff < timedelta(seconds=COOLDOWN_TIME):
            remaining_time = COOLDOWN_TIME - int(time_diff.total_seconds())
            await message.answer(f"⏳ Пожалуйста, подождите {remaining_time} секунд перед повторным выводом средств.")
            return

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance = user[0]
        # Преобразуем balance в float
        balance_float = float(balance)

        balance_formatted = "{:.0f}".format(int(balance_float))

        if balance_float > 1:  # Сравниваем с float
            # Рассчитываем суммы для вывода
            withdraw_10_amount = round(balance_float * 0.10)
            withdraw_25_amount = round(balance_float * 0.25)
            withdraw_50_amount = round(balance_float * 0.50)
            withdraw_100_amount = balance_formatted

            # Создаем кнопки с отображением сумм в $
            withdraw_10_button = KeyboardButton(text=f"💸 Вывести ${withdraw_10_amount}")
            withdraw_25_button = KeyboardButton(text=f"💸 Вывести ${withdraw_25_amount}")
            withdraw_50_button = KeyboardButton(text=f"💸 Вывести ${withdraw_50_amount}")
            withdraw_all_button = KeyboardButton(text=f"💸 Вывести ${withdraw_100_amount}")

            markup = ReplyKeyboardMarkup(
                keyboard=[
                    [withdraw_10_button, withdraw_50_button],
                    [withdraw_25_button, withdraw_all_button]
                ],
                resize_keyboard=True
            )
            balance = "{:.2f}".format(balance)
            await message.answer(f"💰 Ваш баланс: {balance} USDT\nВыберите сумму для вывода:",
                                 reply_markup=markup)
        else:
            await message.answer("🚫 На вашем балансе недостаточно средств для вывода. (Min 1 USDT)")
    else:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")


# Обработчик для кнопки "Вывести $X"
@dp.message(lambda message: message.text.startswith("💸 Вывести $"))
async def withdraw_fixed_amount(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    amount = int(text.split("$")[1])  # Получаем сумму из текста кнопки

    # Рассчитываем процент для вывода
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance = user[0]

        if balance >= amount:
            # Вычисляем процентное соотношение
            percentage = (amount / balance) * 100
            await process_withdrawal(message, percentage)
        else:
            await message.answer(f"🚫 У вас недостаточно средств для вывода {amount} USDT.")


# Общий метод для обработки вывода средств

async def process_withdrawal(message: types.Message, percentage: int):
    user_id = message.from_user.id  # Получаем user_id из сообщения
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance = user[0]

        if balance > 0:
            amount = balance * (percentage / 100)
            commission_rate = 0.05  # Комиссия 5%
            commission = amount * commission_rate
            final_amount = amount - commission

            # Проверка, что сумма вывода не меньше 1 USDT после учета комиссии
            if final_amount < 1:
                await message.answer(
                    "🚫 Невозможно вывести сумму меньше 1 USDT после учета комиссии. Пожалуйста, выберите другую сумму.")
                return

            # Уведомляем пользователя о комиссии
            await message.answer(
                f"💵 Сумма вывода: {amount:.2f} USDT\n"
                f"💼 Комиссия: {commission:.2f} USDT (5%)\n"
                f"🏦 Итого к выводу: {final_amount:.2f} USDT"
            )

            # Проверка баланса приложения
            app_balance = await cryptopay.get_balance()
            usdt_balance = get_balance('USDT', app_balance)

            if usdt_balance >= final_amount:
                # Обновление баланса пользователя
                cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                conn.commit()

                # Перевод средств
                transfer = await cryptopay.transfer(user_id=user_id, asset="USDT", amount=final_amount,
                                                    spend_id=str(uuid.uuid4()))

                # Отправка сообщения пользователю
                await message.answer(f"🏦 Средства в размере {final_amount:.2f} USDT были успешно отправлены вам.",
                                     reply_markup=keyboard.main_menu_markup)
                await message.delete()

                # Логирование действия
                log_action(user_id, "Withdraw", final_amount)

                # Уведомление администраторов
                username = await get_username_by_id(bot, user_id)
                # f"Пользователь: @{username}\n"
                await notify_admins(f"🏦 Вывод средств:\n\nПользователь ID: {user_id}\n"
                                    f"Пользователь: @{username}\n"
                                    f"Сумма: {amount:.2f} USDT\n"
                                    f"Комиссия: {commission:.2f} USDT\n"
                                    f"К выводу: {final_amount:.2f} USDT")
            else:
                # В случае недостатка средств у бота не списываем средства с базы данных
                invoice = await cryptopay.create_invoice(asset='USDT', amount=final_amount - usdt_balance)
                await message.answer("🚫 На счету приложения недостаточно средств для проведения операции.",
                                     reply_markup=keyboard.main_menu_markup)
                await notify_admins(f"🏦 ПОПОЛНИ КАЗНУ!!! \n"
                                    f"НА КАЗНЕ {round(usdt_balance, 1)} USDT\n"
                                    f"Не хватает {round(final_amount - usdt_balance, 1)} USDT\n"
                                    f"{invoice.mini_app_invoice_url}")
        else:
            await message.answer("🚫 На вашем балансе меньше 1 USDT, пополните баланс для вывода.",
                                 reply_markup=keyboard.main_menu_markup)
    else:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.",
                             reply_markup=types.ReplyKeyboardRemove())


##reply_markup=types.ReplyKeyboardRemove()

# Админ-панель
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    admin_id = config.admin_id
    moder_id = config.moder_id
    user_id = message.from_user.id
    # Объединяем всех в один список
    all_ids = [admin_id] + moder_id

    if user_id in all_ids:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Показать всех пользователей 📋", callback_data="show_users")],
            [InlineKeyboardButton(text="💵 Добавить средства пользователю 💳", callback_data="add_funds")],
            [InlineKeyboardButton(text="📊 Статистика казино 📈", callback_data="casino_stats")],
            [InlineKeyboardButton(text="💰 Пополнение казны 🏦", callback_data="replenish_treasure")],
            [InlineKeyboardButton(text="📬 Отправить рассылку всем 📤", callback_data="send_broadcast")]
        ])
        await message.answer("⚙️ Админ-панель:", reply_markup=markup)
    else:
        await message.answer("🚫 У вас нет прав доступа к админ-панели.")


@dp.callback_query(lambda c: c.data == "send_broadcast")
async def process_send_broadcast(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Введите текст сообщения для рассылки: в /send")


from aiogram.exceptions import TelegramBadRequest


@dp.message(Command("send"))
async def send_message_to_all(message: types.Message):
    admin_id = config.admin_id
    moder_id = config.moder_id
    user_id = message.from_user.id
    # Объединяем всех в один список
    all_ids = [admin_id] + moder_id

    if user_id in all_ids:
        # Извлечение текста сообщения
        text_to_send = message.text[6:].strip()  # Убираем команду /send и пробелы

        if text_to_send:
            # Получаем список всех пользователей
            cursor.execute("SELECT user_id, balance FROM users")
            users = cursor.fetchall()
            deleted_count = 0  # Счётчик удалённых пользователей
            deleted_balance_sum = 0  # Счётчик удалённого баланса

            for user_id, balance in users:
                try:
                    await bot.send_message(user_id, text_to_send)
                except TelegramBadRequest:
                    # Удаляем пользователя при любой ошибке TelegramBadRequest
                    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                    conn.commit()
                    deleted_count += 1  # Увеличиваем счётчик при удалении
                    deleted_balance_sum += balance  # Добавляем баланс к сумме удалённых
                except Exception as e:

                    # Удаляем пользователя при любой ошибке TelegramBadRequest
                    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                    conn.commit()
                    deleted_count += 1  # Увеличиваем счётчик при удалении
                    deleted_balance_sum += balance  # Добавляем баланс к сумме удалённых

            await message.answer(f"✅ Сообщение успешно отправлено всем пользователям!\n"
                                 f"Удалено заблокировавших пользователей: {deleted_count}\n"
                                 f"Удалённый баланс: {deleted_balance_sum} 💰")
        else:
            await message.answer("❌ Пожалуйста, введите текст сообщения после команды /send.")
    else:
        await message.answer("🚫 У вас нет прав доступа к этой команде.")


@dp.callback_query(lambda c: c.data == "show_users")
async def show_users(callback_query: types.CallbackQuery):
    admin_id = config.admin_id
    moder_id = config.moder_id
    user_id = callback_query.from_user.id
    # Объединяем всех в один список
    all_ids = [admin_id] + moder_id

    if user_id in all_ids:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        user_list = "\n".join([f"User ID: {user[0]}, Balance: {user[1]} USDT" for user in users])
        await bot.send_message(user_id, f"📄 Список всех пользователей:\n\n{user_list}")
        await callback_query.answer("💰 Сообщение с информацией отправлено в лс.")
    else:
        await callback_query.answer("🚫 У вас нет прав доступа к админ-панели.")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "casino_stats")
async def casino_stats(callback_query: types.CallbackQuery):
    conn2 = sqlite3.connect('casino_log.db')
    cursor2 = conn2.cursor()
    admin_id = config.admin_id
    moder_id = config.moder_id
    user_id = callback_query.from_user.id
    # Объединяем всех в один список
    all_ids = [admin_id] + moder_id

    if user_id in all_ids:
        today = datetime.now().strftime('%Y-%m-%d')
        cursor2.execute("SELECT sum(amount) FROM logs WHERE action='Deposit' AND DATE(timestamp) = ?", (today,))
        daily_deposit = cursor2.fetchone()[0] or 0.0

        cursor2.execute("SELECT sum(amount) FROM logs WHERE action='Withdraw' AND DATE(timestamp) = ?", (today,))
        daily_withdrawal = cursor2.fetchone()[0] or 0.0

        cursor.execute("SELECT sum(balance) FROM users")
        total_user_balance = cursor.fetchone()[0] or 0.0

        cursor2.execute("SELECT sum(amount) FROM logs WHERE action='Deposit'")
        total_deposits = cursor2.fetchone()[0] or 0.0

        cursor2.execute("SELECT sum(amount) FROM logs WHERE action='Withdraw'")
        total_withdrawals = cursor2.fetchone()[0] or 0.0

        # Новый запрос для получения общего количества пользователей
        cursor.execute("SELECT count(*) FROM users")
        total_users = cursor.fetchone()[0] or 0

        app_balance = await cryptopay.get_balance()
        usdt_balance = get_balance('USDT', app_balance)

        message = (
            f"📊 Статистика казино:\n\n"
            f"📅 Дневная статистика ({today}):\n"
            f"💵 Пополнения: {daily_deposit:.2f} USDT\n"
            f"💸 Выводы: {daily_withdrawal:.2f} USDT\n"
            f"📊 Прибыль за день: {daily_deposit - daily_withdrawal:.2f}\n"
            f"📈 Общая статистика:\n"
            f"💰 Баланс пользователей: {total_user_balance:.2f} USDT\n"
            f"👥 Всего пользователей: {total_users}\n"  # Добавлено количество пользователей
            f"💵 Всего пополнений: {total_deposits:.2f} USDT\n"
            f"💸 Всего выводов: {total_withdrawals:.2f} USDT\n\n"
            f"💸 Баланс казино: {usdt_balance:.2f} $"
        )
        await bot.send_message(admin_id, message)
        await callback_query.answer("💰 Сообщение с информацией отправлено в лс.")
    else:
        await callback_query.answer("🚫 У вас нет прав доступа к админ-панели.")
    await callback_query.answer()


class States(StatesGroup):
    awaiting_funds_input = State()


@dp.callback_query(lambda c: c.data == "add_funds")
async def add_funds(callback_query: types.CallbackQuery, state: FSMContext):
    admin_id = config.admin_id
    moder_id = config.moder_id
    user_id = callback_query.from_user.id
    # Объединяем всех в один список
    all_ids = [admin_id] + moder_id

    if user_id in all_ids:
        await callback_query.message.answer(
            "Введите ID пользователя и сумму для добавления средств в формате: <user_id> <amount>")

        # Установка состояния для ожидания ввода данных
        await state.set_state(States.awaiting_funds_input)
    else:
        await callback_query.answer("🚫 У вас нет прав доступа для добавления средств.")


@dp.message(States.awaiting_funds_input)
async def process_funds_input(message: types.Message, state: FSMContext):
    data = message.text.split()

    if len(data) != 2:
        await message.edit_text("🚫 Пожалуйста, введите данные в правильном формате: <user_id> <amount>")
        return

    try:
        user_id = int(data[0])
        amount = float(data[1])
    except ValueError:
        await message.edit_text(
            "🚫 Неправильный формат. Убедитесь, что ID пользователя - это число, а сумма - это десятичное число.")
        return

    if amount <= 0:
        await message.edit_text("🚫 Сумма должна быть положительной.")
        return

    # Проверка существования пользователя в базе данных
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        # Обновление баланса пользователя
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        log_action(user_id, "AddAdminBalace", amount)
        await message.answer(
            f"💵 Средства в размере {amount:.2f} USDT были успешно добавлены пользователю с ID {user_id}.")
        admin_username = message.from_user.username or "Неизвестный"

        # Уведомление администраторов
        username = await get_username_by_id(bot, user_id)

        # Теперь можете использовать переменную username для уведомлений
        await notify_admins(f"🏦 Начисление баланса:\n\n"
                            f"Пользователь ID: {user_id}\n"
                            f"Пользователь: @{username}\n"
                            f"Сумма: {amount:.2f} USDT\n"
                            f"Администратор: @{admin_username}\n"
                            )

        await bot.send_message(user_id, f"🏦 Вам был начислен баланс:\n\n"
                                        f"Сумма: {amount:.2f} USDT\n"
                                        f"Администратор: @{admin_username}")
    else:
        await message.edit_text("🚫 Пользователь с таким ID не найден.")

    # Сброс состояния
    await state.clear()


@dp.callback_query(lambda c: c.data == "replenish_treasure")
async def replenish_treasure(callback_query: types.CallbackQuery):
    admin_id = config.admin_id
    if callback_query.from_user.id == admin_id:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 Пополнить на 500 USDT", callback_data="replenish_500")],
            [InlineKeyboardButton(text="💴 Пополнить на 1000 USDT", callback_data="replenish_1000")],
            [InlineKeyboardButton(text="💰 Пополнить на 5000 USDT", callback_data="replenish_5000")],
            [InlineKeyboardButton(text="🏦 Пополнить на 10000 USDT", callback_data="replenish_10000")]
        ])

        await bot.send_message(admin_id, "💰 Выберите сумму для пополнения казны:", reply_markup=markup)


@dp.callback_query(lambda c: c.data.startswith("replenish_"))
async def process_replenish(callback_query: types.CallbackQuery):
    admin_id = config.admin_id
    if callback_query.from_user.id == admin_id:
        amount = int(callback_query.data.split("_")[1])
        app_balance = await cryptopay.get_balance()
        usdt_balance = get_balance('USDT', app_balance)

        if usdt_balance >= amount:
            # Добавляем средства в базу данных
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id IS NOT NULL", (amount,))
            conn.commit()

            # Логируем пополнение
            log_action(admin_id, "Treasury Replenish", amount)

            invoice = await cryptopay.create_invoice(asset='USDT', amount=amount)

            await bot.send_message(admin_id, f"💰 Оплатите пополнение на {amount:.2f} USDT.\n"
                                             f"{invoice.mini_app_invoice_url}")
            await notify_admins(f"💰 Казна пополнена администратором:\n\nСумма: {amount:.2f} USDT")
        else:
            await bot.send_message(admin_id, "🚫 На счету приложения недостаточно средств для проведения операции.")
            invoice = await cryptopay.create_invoice(asset='USDT', amount=amount - usdt_balance)
            await bot.send_message(admin_id, f"🔗 Счёт для пополнения казны:\n{invoice.mini_app_invoice_url}")

    await callback_query.answer()


@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "ℹ️ Помощь по игре\n\n"
        "1. /play - Начать игру в кубик.\n\n"
        "2. Выбор режима игры:\n"
        "   - Чет/Нечет: Выберите, хотите ли вы ставить на четное или нечетное число. Если число совпадает с вашим выбором, вы выиграете ставку.\n"
        "   - Больше/Меньше: Выберите, хотите ли вы ставить на то, что выпадет число 4 или выше, или 3 и ниже. Если ваше предположение верно, вы выиграете ставку.\n\n"
        "3. Ставка:\n"
        "   - Выберите сумму ставки из предложенных вариантов (1 USDT, 5 USDT, 10 USDT).\n\n"
        "4. Баланс:\n"
        "   - Ваш баланс обновляется после каждой игры. Выигрыши добавляются к вашему балансу, а проигрыши вычитаются.\n\n"
        "5. Система чеков:\n"
        "   - Вы можете создавать чеки на определенную сумму, которые могут быть активированы другими пользователями.\n"
        "   - Для создания чека используйте команду /check, указав сумму и, при необходимости, количество активаций или @username для конкретного пользователя.\n"
        "   - Чеки могут быть активированы только один раз каждым пользователем. Убедитесь, что у вас достаточно средств на счете для создания чеков.\n\n"
        "📊 Команды:\n"
        "   - /profile: Просмотреть информацию о вашем профиле и текущем балансе.\n"
        "   - /deposit: Пополнить баланс.\n"
        "   - /outbalance: Вывод средств.\n"
        "   - /help: Получить помощь и инструкции по игре.\n\n"
        "❓ Если у вас есть вопросы, не стесняйтесь спрашивать!"
    )

    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓Поддержка", url=f"https://t.me/{config.ADMIN_USERNAME}")]
    ])
    await message.answer(help_text, reply_markup=inline_keyboard)


@dp.message(Command("profile"))
async def profile(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    username = message.from_user.username or "Не задан"

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance = user[0]
        await message.answer(
            f"👤 Ваш профиль\n\n"
            f"🆔 ID: {user_id}\n"
            f"👤 Имя: {first_name} {last_name}\n"
            f"📛 Юзернейм: @{username}\n"
            f"💰 Баланс: {balance} USDT"
        )
    else:
        await message.answer("🚫 Вы не зарегистрированы. Используйте /start для регистрации.")


async def notify_win(user_name: str, win_amount: float, stake_amount: float, user_id: int, bet_choice: str,
                     is_win: bool):
    win_chat_id = config.win_id

    quotes = [
        "🎲 Все или ничего — делай ставку и верь в свою победу!",
        "🔥 Сегодня твой день! Пусть удача сверкает на каждом шагу!",
        "💰 Чем больше риск, тем слаще награда! Ставь и не оглядывайся!",
        "🎉 В казино есть два типа людей: те, кто выигрывают, и те, кто просто ждут!",
        "🌟 Почувствуй азарт, ведь следующая ставка может стать судьбоносной!",
        "💥 Каждый спин — это шанс изменить всё! Не упусти его!",
        "💸 Деньги любят смелых! Сделай ход, пока удача на твоей стороне!",
        "🎯 Один бросок может перевернуть игру! Играем?",
        "🏆 Победа ждёт тех, кто не боится рисковать! Вперёд за адреналином!",
        "🍀 Везение приходит к тем, кто готов рискнуть всем! Готов?",
        "🃏 В казино выигрывают те, кто верит в свою интуицию! Сделай ход!",
        "🔥 Азарт — это язык победителей. Время сделать ставку!",
        "💥 Вся магия в моменте, когда ставка уже сделана! Почувствуй её!",
        "🎰 Следующий спин может принести тебе всё, о чём мечтал! Действуй!",
        "💸 Не жди удачи — создай её сам! Сделай ставку и выиграй!",
        "💪 Ставь высоко или смотри, как это делают другие! Риск — твой друг!",
        "🍾 Победа сладка, но азарт — вот что действительно захватывает!",
        "🎲 С каждым броском кубиков ты всё ближе к джекпоту! Вперёд!",
        "🌠 Сегодня — твой день! Удача уже рядом, осталось только сделать шаг!",
        "💥 В казино ты сам себе хозяин! Пусть твоя смелость приведёт к успеху!",
    ]

    result_status = f"выигрыш (+{int(stake_amount * 0.8)}$)" if is_win else f"проигрыш (-{int(stake_amount)}$)"

    if bet_choice.capitalize() == "Коробки📦":
        result_status = f"выигрыш (+{int(stake_amount * 1)}$)" if is_win else f"проигрыш (-{int(stake_amount)}$)"

    if bet_choice.capitalize() == "🎰777 в ряд!":
        result_status = f"выигрыш (+{int(stake_amount * 9)}$)" if is_win else f"проигрыш (-{int(stake_amount)}$)"

    if bet_choice.capitalize() == "🎰3 в ряд!":
        result_status = f"выигрыш (+{int(stake_amount * 4)}$)" if is_win else f"проигрыш (-{int(stake_amount)}$)"

    user_prefix = get_user_prefix(user_id)
    prefix_set = (prefixes[int(user_prefix)]['name'])

    #global result_message
    if user_prefix == "10":
        result_message = (
            f"{prefix_set}: @{user_name} (ID: <a href='tg://user?id={user_id}'>{user_id}</a>)\n"
            f"💰 Ставка: <b>{stake_amount:.1f} $</b>\n"
            f"🎲 Исход: <i>{bet_choice.capitalize()}</i>\n"
            f"🚀 Итог ставки: <b>{result_status}</b>\n"
            f"<blockquote>\"{random.choice(quotes)}\"</blockquote>\n"
        )
    else:
        result_message = (
            f"{prefix_set}: @{user_name} (ID: <a href='tg://user?id={user_id}'>{user_id}</a>)\n"
            f"💵 Сумма ставки: <b>{stake_amount:.1f} $</b>\n"
            f"🎲 Выбор: <i>{bet_choice.capitalize()}</i>\n"
            f"🏆 Результат: <b>{result_status}</b>\n"
            f"<blockquote>\"{random.choice(quotes)}\"</blockquote>\n"
        )

    if is_win:
        photo = FSInputFile('res/win.jpg')
    else:
        photo = FSInputFile('res/lose.jpg')

    # Создаем инлайн-кнопку
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Играть снова", url=f"https://t.me/{config.BOT_USERNAME}")]
    ])

    # Отправляем сообщение в чат с инлайн-кнопкой
    await bot.send_photo(
        photo=photo,
        chat_id=win_chat_id,
        caption=result_message,
        reply_markup=inline_keyboard,
        parse_mode='HTML'  # Используйте HTML для форматирования текста
    )


app_balance = cryptopay.get_balance()


async def get_username_by_id(bot: Bot, user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        return user.username if user.username else "Неизвестный"
    except Exception as e:
        return "Ошибка"


def get_balance(currency_code, balances):
    for balance in balances:
        if balance.currency_code == currency_code:
            return float(balance.available)  # Преобразование в float
    return None  # если валюты нет в списке


def get_user_info(user_id):
    conn = sqlite3.connect('casino_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_info = cursor.fetchone()
    conn.close()
    return user_info


def get_referrals(user_id):
    referral_conn = sqlite3.connect(config.REFERRAL_FILE)
    referral_cursor = referral_conn.cursor()
    referral_cursor.execute('SELECT * FROM referrals WHERE referrer_user_id = ?', (user_id,))
    referrals = referral_cursor.fetchall()
    referral_conn.close()
    return referrals


def get_logs(user_id):
    log_conn = sqlite3.connect(config.LOG_FILE)
    log_cursor = log_conn.cursor()
    log_cursor.execute('SELECT * FROM logs WHERE user_id = ?', (user_id,))
    logs = log_cursor.fetchall()
    log_conn.close()
    return logs


ADMIN_USER_IDS = {config.admin_id}


@dp.message(Command("info"))
async def info_command(message: types.Message):
    args = message.text.split()

    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Пожалуйста, укажите корректный ID пользователя.")
        return

    user_id = int(args[1])

    if message.from_user.id not in ADMIN_USER_IDS:
        await message.answer("У вас нет доступа к этой команде.")
        return

    user_info = get_user_info(user_id)
    referrals = get_referrals(user_id)
    logs = get_logs(user_id)
    checks = get_checks(user_id)  # Функция для получения чеков

    if user_info is None:
        await message.answer("🚫 Пользователь не найден.")
        return

    response = f"✨ Информация о пользователе ✨\n"
    response += f"🔹 ID: {user_info[0]}\n"
    response += f"🔹 Имя пользователя: @{await get_username_by_id(bot, user_info[0])}\n"
    response += f"🔹 Баланс: {user_info[1]:.2f} 💰\n"
    response += "🔹 Рефералы:\n"

    if referrals:
        for referral in referrals:
            response += f"  - Код: {referral[2]} 🆔, ID приглашённого: {referral[3]} 👤, Статус: {referral[4]} ✅\n"
    else:
        response += "  - Нет рефералов. ❌\n"

    response += "\n🔹 Логи:\n"

    if logs:
        # Получаем последние 10 логов
        recent_logs = logs[-10:]  # Срез последних 10 элементов
        for log in recent_logs:
            response += f"  - Действие: {log[2]} 🔄, Сумма: {log[3]:.2f} 💵, Время: {log[4]} ⏰\n"
    else:
        response += "  - Нет логов. 📜\n"

    response += "\n🔹 Чеки:\n"

    if checks:
        for check in checks:
            response += f"  - Код: {check[2]} 🏷️, Сумма: {check[3]} 💵, Остаток: {check[6]} 🎟️\n"
    else:
        response += "  - Нет чеков. 📜\n"

    response += "\n" + "-" * 40 + "\n"  # Разделитель
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response += f"<b>📅 Дата и время запроса:</b> {current_time} 📅"
    #user_info[0]

    if is_user_locked(user_info[0]):
        text_lock = "[✅] Разблокировать пользователя"
        status2 = "unblock"
    else:
        text_lock = "[❌]  Заблокировать пользователя"
        status2 = "block"

    if is_withdrawal_locked(user_info[0]):
        text_out = "[✅] Разблокировать вывод"
        status = "unblock"
    else:
        text_out = "[❌] Заблокировать вывод"
        status = "block"

    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text_lock, callback_data=f"{status2}_user_{user_info[0]}")],
        [InlineKeyboardButton(text=text_out, callback_data=f"{status}_out_{user_info[0]}")]
    ])

    await message.answer(response, reply_markup=inline_keyboard, parse_mode='HTML')


# Определяем текстовые и callback переменные
def get_lock_button_info(user_id):
    if is_user_locked(user_id):
        return "[✅] Разблокировать пользователя", "unblock_user"
    else:
        return "[❌] Заблокировать пользователя", "block_user"


def get_withdrawal_button_info(user_id):
    if is_withdrawal_locked(user_id):
        return "[✅] Разблокировать вывод", "unblock_out"
    else:
        return "[❌] Заблокировать вывод", "block_out"


# Callback handler for user locking/unlocking
@dp.callback_query(lambda c: c.data.startswith(('block_user_', 'unblock_user_')))
async def toggle_user_lock(callback_query: types.CallbackQuery):
    action, user_id = callback_query.data.rsplit('_', 1)  # Разделяем только по последнему символу '_'
    user_id = int(user_id)

    if action == 'block_user':
        lock_user(user_id)
        await callback_query.answer("Пользователь заблокирован.")
    elif action == 'unblock_user':
        unlock_user(user_id)
        await callback_query.answer("Пользователь разблокирован.")

    # Получаем обновленные тексты и данные для кнопок
    text_lock, lock_action = get_lock_button_info(user_id)
    text_out, withdrawal_action = get_withdrawal_button_info(user_id)

    # Обновляем клавиатуру
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text_lock, callback_data=f"{lock_action}_{user_id}")],
        [InlineKeyboardButton(text=text_out, callback_data=f"{withdrawal_action}_{user_id}")]
    ])

    await callback_query.message.edit_reply_markup(reply_markup=inline_keyboard)


# Callback handler for withdrawal locking/unlocking
@dp.callback_query(lambda c: c.data.startswith(('block_out_', 'unblock_out_')))
async def toggle_withdrawal_lock(callback_query: types.CallbackQuery):
    action, user_id = callback_query.data.rsplit('_', 1)  # Разделяем только по последнему символу '_'
    user_id = int(user_id)

    if action == 'block_out':
        lock_withdrawal(user_id)
        await callback_query.answer("Вывод заблокирован.")
    elif action == 'unblock_out':
        unlock_withdrawal(user_id)
        await callback_query.answer("Вывод разблокирован.")

    # Получаем обновленные тексты и данные для кнопок
    text_lock, lock_action = get_lock_button_info(user_id)
    text_out, withdrawal_action = get_withdrawal_button_info(user_id)

    # Обновляем клавиатуру
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text_lock, callback_data=f"{lock_action}_{user_id}")],
        [InlineKeyboardButton(text=text_out, callback_data=f"{withdrawal_action}_{user_id}")]
    ])

    await callback_query.message.edit_reply_markup(reply_markup=inline_keyboard)


# Функция для получения чеков
def get_checks(user_id):
    # Подключаемся к базе данных казино
    conn = sqlite3.connect('casino_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM checks WHERE creator_id = ?', (user_id,))
    checks = cursor.fetchall()
    conn.close()
    return checks


@dp.message(Command("clear_checks"))
async def clear_checks_command(message: types.Message):
    if message.from_user.id not in ADMIN_USER_IDS:
        await message.answer("У вас нет доступа к этой команде.")
        return

    clear_checks()  # Очищаем таблицу чеков
    await message.answer("✅ Все чеки были успешно очищены.")


def clear_checks():
    conn = sqlite3.connect('casino_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM checks')
    conn.commit()
    conn.close()


casino_conn = sqlite3.connect('casino_bot.db')
casino_cursor = casino_conn.cursor()

log_conn = sqlite3.connect(config.LOG_FILE)
log_cursor = log_conn.cursor()

referral_conn = sqlite3.connect(config.REFERRAL_FILE)
referral_cursor = referral_conn.cursor()


@dp.message(Command("delete"))
async def delete_user(message: types.Message):
    try:
        ADMIN_IDS = [config.admin_id]  # Убедитесь, что admin_id - это корректный ID
        # Проверка, является ли пользователь администратором
        if message.from_user.id not in ADMIN_IDS:
            await message.reply('🚫 У вас нет прав для выполнения этой команды.')
            return

        args = message.text.split()
        # Извлекаем ID пользователя из команды
        if len(args) < 2:
            await message.reply('⚠️ Пожалуйста, укажите ID пользователя для удаления.')
            return

        user_id = int(args[1])

        # Получаем статистику пользователя перед удалением
        user_stats = casino_cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if user_stats:
            balance = user_stats[0]
        else:
            balance = None

        # Удаляем записи из таблицы checks в базе данных casino_bot
        checks_deleted = casino_cursor.execute('DELETE FROM checks WHERE creator_id = ?', (user_id,)).rowcount

        # Удаляем записи из таблицы logs в базе данных casino_log
        logs_deleted = log_cursor.execute('DELETE FROM logs WHERE user_id = ?', (user_id,)).rowcount

        # Удаляем записи из таблицы referrals в базе данных referrals
        referrals_deleted = referral_cursor.execute(
            'DELETE FROM referrals WHERE referrer_user_id = ? OR referred_user_id = ?',
            (user_id, user_id)).rowcount

        # Удаляем пользователя из базы данных casino_bot
        user_deleted = casino_cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,)).rowcount
        casino_conn.commit()

        # Подготовка сообщения с информацией о том, что было удалено
        info = f'🗑️ Пользователь с ID {user_id} был успешно удалён.\n'
        info += f'✅ Удалено чеков: {checks_deleted}\n'
        info += f'✅ Удалено логов: {logs_deleted}\n'
        info += f'✅ Удалено рефералов: {referrals_deleted}\n'

        # Добавляем статистику пользователя
        if balance is not None:
            info += f'💰 Баланс удалённого пользователя: {balance}\n'
        else:
            info += '❌ Статистика не найдена.\n'

        # Проверка, был ли пользователь удален
        if user_deleted > 0:
            await message.reply(info)
        else:
            await message.reply(f'❌ Пользователь с ID {user_id} не найден.')

    except ValueError:
        await message.reply('⚠️ Пожалуйста, укажите корректный ID пользователя.')
    except Exception as e:
        await message.reply(f'⚠️ Произошла ошибка: {str(e)}')
    finally:
        # Закрываем соединения с базами данных
        casino_conn.close()
        log_conn.close()
        referral_conn.close()


def is_user_locked(user_id):
    cursor.execute("SELECT is_locked FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result is not None:
        return bool(result[0])  # Вернем True, если заблокирован, иначе False
    return False  # Если пользователь не найден


def is_withdrawal_locked(user_id):
    cursor.execute("SELECT withdrawal_locked FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result is not None:
        return bool(result[0])  # Вернем True, если блокировка вывода активна, иначе False
    return False  # Если пользователь не найден


def lock_user(user_id):
    cursor.execute("UPDATE users SET is_locked = 1 WHERE user_id=?", (user_id,))
    conn.commit()


def unlock_user(user_id):
    cursor.execute("UPDATE users SET is_locked = 0 WHERE user_id=?", (user_id,))
    conn.commit()


def lock_withdrawal(user_id):
    cursor.execute("UPDATE users SET withdrawal_locked = 1 WHERE user_id=?", (user_id,))
    conn.commit()


def unlock_withdrawal(user_id):
    cursor.execute("UPDATE users SET withdrawal_locked = 0 WHERE user_id=?", (user_id,))
    conn.commit()


@dp.message(Command("restart"))
async def restart_bot(message: types.Message):
    admin_id = config.admin_id
    if message.from_user.id == admin_id:
        await message.answer("🔄 Перезагрузка бота...")
        # Перезагрузка скрипта
        os.execv(sys.executable, ['python'] + sys.argv)
    else:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")


@dp.message(Command("halava"))
async def distribution(message: types.Message):
    amount = random.randint(int(10), 50)
    #amount = f"{amount}"
    check = await(cryptopay.create_check(asset="USDT", amount=amount))
    text = f"🦋 Чек на {amount} USDT (${amount})."
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Получить {amount} USDT ", url=check.bot_check_url)]
    ])
    check_id = check.check_id

    message = await bot.send_message(chat_id=config.win_id, text=text, reply_markup=inline_keyboard)
    await bot.send_message(chat_id=config.admin_id, text="check", reply_markup=inline_keyboard)
    save = message.message_id

    a = True
    while a:
        check = await cryptopay.get_checks()
        target_check = next((check for check in check if check.check_id == check_id), None)
        if target_check.status == "activated":
            await bot.delete_message(chat_id=config.win_id, message_id=save)
            await bot.send_message(chat_id=config.admin_id, text=f"Чек №{check_id} был успешно активирован")
            a = False


async def create_checka(amount, activations):
    # Параметры по умолчанию
    user_id = config.admin_id  # Пример ID пользователя (поменяйте на актуальное значение)
    recipient_username = None  # По умолчанию чек доступен всем

    # Если количество активаций не указано, считаем, что их бесконечно
    if activations is None:
        activations = 0  # Если 0, значит, активаций может быть бесконечно

    # Генерируем уникальный код чека
    check_code = str(uuid.uuid4())[:8]

    # Добавляем запись в таблицу чеков (замените на свой запрос)
    cursor.execute('''INSERT INTO checks (creator_id, check_code, amount, max_activations, remaining_activations, recipient_username) 
                      VALUES (?, ?, ?, ?, ?, ?)''',
                   (user_id, check_code, amount, activations, activations, recipient_username))
    conn.commit()

    # Генерация ссылки на активацию
    check_link = f"https://t.me/{config.BOT_USERNAME}?start=check_{check_code}"

    # Возвращаем ссылку
    return check_link


@dp.message(Command("vhalava"))
async def distribution2(message: types.Message):
    args = message.text.split()
    if args == ['/vhalava']:
        await bot.send_message(chat_id=message.from_user.id, text="Ты долбаеб укажи сумму раздачи")
    else:
        amount = args[1]
        message = (
            f"🎉 <b>Скоро начнется раздача чека на сумму {amount} USDT</b> 🎉\n\n"
            f"🔜 <b>Подготовьтесь к участию в акции!</b> 🔜\n\n"
            f"💡 <i>Как это работает?</i>\n"
            f"1. Раздача будет проходить в несколько этапов, не упустите свой шанс!\n"
            f"2.Каждый чек на сумму <b>{amount} USDT</b> будет доступен для активации с уникальной ссылкой.\n"
            f"3. Будьте внимательны — количество активаций ограничено!\n\n"
            f"⏳ <b>Таймер уже запущен...</b> ⏳\n\n"
            f"🔔 <b>Подготовьтесь к раздаче и не пропустите свой шанс!</b> 🔔\n\n"
            f"✨ Следите за обновлениями и ожидайте свою ссылку на активацию чека! ✨"
        )
        message = await bot.send_message(config.win_id, message, parse_mode="HTML")
        message_id = message.message_id

        time.sleep(random.randint(10, 60))
        all_activation = random.randint(5, 20)
        check_amount = int(amount) / all_activation
        check_amount = "{:.2f}".format(check_amount)

        await bot.delete_message(chat_id=config.win_id, message_id=message_id)

        message = (
            "<b>⏰ Время подошло! Раздача начинается прямо сейчас! ⏰</b>\n"
            "<b>🎉 Начинается раздача чеков! 🎉</b>\n\n"
            f"<b>🔑 Чеки на сумму <strong>{check_amount} USDT</strong> теперь доступны для активации!</b>\n"
            "🔗 Следите за обновлениями, чтобы не пропустить свою ссылку на чек! 🔜\n\n"
            "💡 Не упустите шанс активировать чек, ведь количество активаций ограничено! 🔥\n\n"
            "⏳ До следующей раздачи осталось немного времени, поэтому будьте внимательны! ⏳\n\n"
            "🚀 Удачи всем участникам! Пусть удача будет на вашей стороне! 🍀"
        )

        message = await bot.send_message(config.win_id, message, parse_mode="HTML")
        message_id = message.message_id
        time.sleep(5)
        await bot.delete_message(chat_id=config.win_id, message_id=message_id)
        activation = all_activation
        check_link = await(create_checka(check_amount, activation))
        message = (
            f"🎉 **ссылка на чек!** 🎉\n\n"
            f"💸 <b>Сумма чека:</b> {check_amount} USDT\n"
            f"🔑 <b>Количество активаций:</b> {activation} раз(а)\n\n"
            f"🔗 <b>Нажмите на кнопку ниже, чтобы активировать чек!</b>\n\n"
            f"<a href='{check_link}'>Активировать чек</a>\n\n"
            f"🚀 Успейте активировать чек, пока не закончились активации! 💥"
        )
        message = await bot.send_message(config.win_id, message, parse_mode="HTML")
        message_id = message.message_id


@dp.message(lambda message: message.text == "🔥Наш Форум")
async def paket_forum(message: Message):
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🔥Посетить наш форум💫",
        url="https://crmp-paket.ru"
    ))

    # Отправляем сообщение
    await message.answer(
        "✨ Дорогой пользователь, ✨\n\n"
        "Мы приглашаем вас посетить наш форум, где вы найдете множество полезной информации о наших проектах.\n"
        "Загляните и узнайте больше! 😉",
        reply_markup=builder.as_markup()
    )

@dp.message(lambda message: message.text == "⭐Купить рекламу")
async def paket_ads(message: Message):
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🔥Написать",
        url=f"https://t.me/{config.ADMIN_USERNAME}"
    ))

    cursor.execute("SELECT count(*) FROM users")
    total_users = cursor.fetchone()[0] or 0

    # Отправляем сообщение
    await message.answer(
        "Хотите разместить свою рекламу? 🔥\n"
        f"Вашу рекламу увидят {total_users} Человек(а)!\n"
        "Нажмите на кнопку ниже, чтобы связаться с нами и обсудить детали! 👇",
        reply_markup=builder.as_markup()
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
