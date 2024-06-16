import os
import discord
from dotenv import load_dotenv

from logger import logger, setup_logger

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)



@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.content == 'test':
        await message.channel.send('Working perfectly!')



def main() -> None:
    setup_logger()
    load_dotenv()
    token = os.getenv('TOKEN')
    if not token:
        raise ValueError('Discord not found in environment')
    bot.run(token, log_handler=None)

if __name__ == "__main__":
    main()
