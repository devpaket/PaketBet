from dotenv import load_dotenv
from os import getenv
from dataclasses import dataclass

load_dotenv()
@dataclass
class BotConfig:
    token: str
    database: str
    bot_username: str

@dataclass
class Config:
    bot: BotConfig

def load_config() -> Config:
    return Config(
        bot=BotConfig(
            token=getenv("BOT_TOKEN"),
            database=getenv("DB_PATH"),
            bot_username=getenv("BOT_USERNAME")
        )
    )
