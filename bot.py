from logger import logger
import os
import discord
from discord.ext import commands

class Bot(commands.Bot):
    def __init__(self, *, intents: discord.Intents, **options) -> None:
        super().__init__(command_prefix=Bot._no_prefix, intents=intents, **options)

    @staticmethod
    def _no_prefix(bot: commands.Bot, message: discord.Message) -> str:
        return "<" if message.content.startswith(">") else ">"
    
    async def on_ready(self):
        await self.sync_commands()
        logger.info(f"Logged in as {self.user}")
    
    async def setup_hook(self) -> None:
        self.tree.clear_commands(guild=None)

        # Load the cogs
        for filename in os.listdir("cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
    
    async def sync_commands(self):
        await self.wait_until_ready()

        # Sync local commands and copy global ones
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            except discord.Forbidden:
                logger.warning(f"Bot is missing permissions to sync commands in {guild.name}")

        logger.info("Commands synchronized.")
