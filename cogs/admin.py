import os
import subprocess
import discord
from discord import app_commands
from discord.ext import commands

from logger import logger


admin_id: int | None = os.getenv('ADMIN_ID', None) # type: ignore
if isinstance(admin_id, str):
    admin_id = int(admin_id)

def _is_bot_admin(interaction: discord.Interaction) -> bool:
    return not interaction.user.bot and interaction.user.id == admin_id


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info(f"Cog {__class__.__name__} ready")
    
    @app_commands.command(
        description="Restarts the bot. Restricted to BOT ADMIN."
    )
    @app_commands.dm_only()
    @app_commands.check(_is_bot_admin)
    async def restart(self, context: discord.Interaction):
        channel: discord.DMChannel = context.channel # type: ignore
        await context.response.send_message("Restarting...")

        try:
            process = subprocess.run(
                "bash -e update.sh",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if process.returncode:
                await channel.send(f"Failure:\n```{process.stderr.decode()}```")

        except subprocess.SubprocessError as e:
            await channel.send(f"`{e.__class__.__name__}: {e}`")
    
    @restart.error
    async def restart_error(self, context: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if admin_id:
                message = f"Only <@{admin_id}> is allowed to use this command."
            else:
                message = "You are not allowed to use this command."
            await context.response.send_message(message, ephemeral=True)
