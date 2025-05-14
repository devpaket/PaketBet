from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

balance_button = KeyboardButton(text="💰 Баланс")
play_button = KeyboardButton(text="🎮 Играть")
deposit_button = KeyboardButton(text="💳 Пополнить")
withdraw_button = KeyboardButton(text="🏦 Вывод")
refferal_button = KeyboardButton(text="🎉 Рефералы")
cashback_button = KeyboardButton(text="🎅 Адвент календарь")
prefix_button = KeyboardButton(text="👻Префиксы")
crmp_button = KeyboardButton(text="🔥Наш Форум")
ads_button = KeyboardButton(text="⭐Купить рекламу")

main_menu_markup = ReplyKeyboardMarkup(
    keyboard=[
        [balance_button, play_button],
        [deposit_button, withdraw_button],
        [refferal_button, cashback_button],
        [prefix_button, ads_button]
    ],
    resize_keyboard=True
)

