import os
import discord
from discord.ext import commands

class Bot(commands.Bot):
    def __init__(self, *, intents: discord.Intents, **options) -> None:
        super().__init__(command_prefix=Bot._no_prefix, intents=intents, **options)

    @staticmethod
    def _no_prefix(bot: commands.Bot, message: discord.Message) -> str:
        return "<" if message.content.startswith(">") else ">"
    
    async def setup_hook(self) -> None:
        # Load the cogs
        for filename in os.listdir("cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
