import os
import discord
from dotenv import load_dotenv

from bot import Bot
from logger import setup_logger

intents = discord.Intents.default()
intents.message_content = True

bot = Bot(intents=intents)



def main() -> None:
    setup_logger()

    load_dotenv()
    token = os.getenv('TOKEN')
    if not token:
        raise ValueError('Discord not found in environment')

    bot.run(token, log_handler=None)

if __name__ == "__main__":
    main()
