import random

async def generate_random_account_number(length: int = 6) -> int:
    if length < 1:
        raise ValueError("Длина номера счета должна быть положительным числом")
    start = 10**(length - 1)
    end = 10**length - 1
    return random.randint(start, end)

def format_name_link(user) -> str:
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", "Пользователь")
    if username:
        return f"<a href='https://t.me/{username}'>{first_name}</a>"
    else:
        return first_name