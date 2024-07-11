import datetime
import discord
from discord import app_commands
from discord.ext import commands

from logger import logger


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        bot.tree.add_command(app_commands.ContextMenu(
            name="Cleanup messages (24h)",
            callback=self.cleanup_messages
        ))

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info(f"Cog {__class__.__name__} ready")
    
    async def cleanup_messages(self, interaction: discord.Interaction, user: discord.Member):
        PERIOD = datetime.timedelta(days=1)
        start_date = interaction.created_at - PERIOD

        guild = interaction.guild
        if guild is None:
            return
        await interaction.response.defer(ephemeral=True)
        
        bot_member: discord.Member = guild.get_member(self.bot.user.id) # type: ignore

        # Check in every channel
        count = 0
        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue
            if not channel.permissions_for(bot_member).manage_messages:
                continue

            messages: list[discord.Message] = []
            async for message in channel.history(after=start_date):
                if message.author.id == user.id:
                    messages.append(message)
        
            # Delete by batch
            LIMIT = 100
            for i in range(0, len(messages), LIMIT):
                selected = messages[i*LIMIT:i*LIMIT+LIMIT]
                await channel.delete_messages(selected)
                count += len(selected)
        
        await interaction.followup.send(f"Deleted {count} messages from {user.mention}")
