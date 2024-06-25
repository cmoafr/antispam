import discord
from discord.ext import commands

from logger import logger


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SpamDetector(bot))

class SpamDetector(commands.Cog):
    GC_AFTER = 25 # Remove messages from history if they are more than X seconds old

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.history: list[discord.Message] = []

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info(f"Cog {__class__.__name__} ready")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or isinstance(message.author, discord.User):
            return
        
        if self._is_spam(message):
            try:
                await message.author.timeout(None, reason="Spam")
                await self._cleanup_messages(message)
            except discord.Forbidden:
                logger.error(f"Missing permissions to timeout {message.author}")

        # Update history
        self.history.append(message)
        while self.history:
            delta = message.created_at - self.history[0].created_at
            if delta.total_seconds() <= self.GC_AFTER:
                break
            self.history.pop(0)

    def _is_spam(self, message: discord.Message) -> bool:
        # Common message filters
        from_author = [msg for msg in self.history if msg.author.id == message.author.id]
        same_content = [msg for msg in from_author if msg.content == message.content]

        # Count messages
        if not same_content:
            return False
        nb_msg = len(same_content)
        nb_same_chan = len(set(msg.channel.id for msg in same_content))
        nb_diff_chan = len(set(msg.channel.id for msg in same_content))

        oldest = min(msg.created_at for msg in same_content)
        timespan = (message.created_at - oldest).total_seconds()

        # Same message in 2 different channels in less than 5 seconds
        if nb_same_chan == nb_msg and nb_msg >= 2 and timespan <= 5:
            return True
        
        # Same message 5 times in the same channel in less than 20 seconds
        if nb_diff_chan == 1 and nb_msg >= 5 and timespan <= 20:
            return True
        
        return False
    
    async def _cleanup_messages(self, original_message: discord.Message):
        if original_message.guild is None:
            return

        for msg in self.history:
            # Must be from this person
            if msg.author.id != original_message.author.id:
                continue
            # In the same guild
            if not msg.guild or msg.guild.id != original_message.guild.id:
                continue
            # And the bot must be able to delete the message
            if msg.channel.permissions_for(msg.guild.me).manage_messages:
                try:
                    await msg.delete()
                except Exception:
                    logger.error(f"Failed to delete message {msg.jump_url}")
            else:
                # TODO: Warn server admins
                logger.error(f"Lack permissions to delete message {msg.jump_url}")
