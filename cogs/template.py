import discord
from discord.ext import commands

from logger import logger


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Template(bot))

class Template(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info(f"Cog {__class__.__name__} ready")
    
    # TODO