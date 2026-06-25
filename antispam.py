import logging
import os
from random import sample
import re
import sys
import traceback
from datetime import timedelta
from enum import Enum

import discord
from cachetools import TTLCache
from discord import Guild, Interaction, Member, Message, TextChannel, User
from dotenv import load_dotenv
# TODO: Proper config
from temp_private_config import (ADMIN_ID, MODERATION_CHANNELS_IDS,
                                 TRAP_CHANNEL_IDS)

MIN_CHANNELS_DURATION = timedelta(seconds=5)
MAX_CHANNELS_COUNT = 3
IDENTICAL_LIMIT = 3
TIMEOUT_DURATION = timedelta(days=7)



class Reason(Enum):
	TESTING = "Don't mind me, just testing the bot"
	OK = "All clear"
	TRAP_CHANNEL = "Trap channel"
	MULTIPLE_CHANNELS_TOO_QUICK = "Spam"
	DUPLICATE_MESSAGE = "Spam"



def can_bypass(user: User | Member) -> bool:
	return user.bot or user.id == ADMIN_ID

async def fetch_member(guild: Guild, user: User | Member | int) -> Member | None:
	if isinstance(user, Member):
		return user

	if isinstance(user, User):
		user = user.id

	member = guild.get_member(user)
	if member is not None:
		return member

	try:
		return await guild.fetch_member(user)
	except discord.NotFound:
		return None

async def fetch_member_in_guilds(client: discord.Client, user_id: int) -> list[Member]:
	guilds = client.guilds

	user = client.get_user(user_id)
	if user is not None and user.mutual_guilds:
		guilds = user.mutual_guilds

	return [
		member for guild in guilds
		if (member := await fetch_member(guild, user_id)) is not None
	]



class Antispam(discord.Client):
	logger: logging.Logger
	admin: User | None
	recent_messages: TTLCache[Message, Message]
	recent_spammers: TTLCache[int, int]

	def __init__(self) -> None:
		self.logger = logging.getLogger("antispam")
		self.logger.setLevel(logging.INFO)
		self.recent_messages = TTLCache(maxsize=100, ttl=60)
		self.recent_spammers = TTLCache(maxsize=50, ttl=60)

		intents = discord.Intents.default()
		intents.guild_messages = True # Receive messages
		intents.message_content = True # Receive content of messages
		intents.members = True # Receive member changes

		member_cache = discord.MemberCacheFlags.from_intents(intents)

		super().__init__(intents=intents, member_cache_flags=member_cache)

	async def on_ready(self) -> None:
		await self.wait_until_ready()

		self.admin = await self.fetch_user(ADMIN_ID)

		self.logger.info("Ready")
		self.logger.info(f"Connected to {len(self.guilds)} guilds")
		await self.admin.send("Connected")

	async def on_error(self, event_method: str, *args, **kwargs) -> None:
		_, e, _ = sys.exc_info()

		self.logger.exception(e)

		if self.admin is not None and e is not None:
			content = "\n".join(traceback.format_exception(e)) or str(e)
			if len(content) > 2000:
				content = content[:800] + "\n\n...\n\n" + content[-800:]
			await self.admin.send(content)

		return await super().on_error(event_method)

	async def on_message(self, message: Message) -> None:
		if not self.is_ready():
			return

		self.logger.debug(f"Received message from {message.author.name} in {message.channel.name if isinstance(message.channel, discord.TextChannel) else '?'}") # DEBUG

		# TODO: Proper handling
		if message.author.id == ADMIN_ID and message.content.startswith("spamdebug "):
			self.logger.setLevel(logging.DEBUG if message.content == "spamdebug on" else logging.INFO)
			await message.delete()
			return

		# TEMP
		if message.author.id == ADMIN_ID and message.content == "buttontest":
			view = build_view(message)
			await message.reply(view=view, mention_author=False)
			return

		self.recent_messages[message] = message
		if message.author.id in self.recent_spammers:
			# No need to deal with them a second time
			return

		reason = self.analyze(message)
		self.logger.debug(f"Reason: {reason.name}") # DEBUG
		if reason == Reason.OK:
			return

		self.recent_spammers[message.author.id] = message.author.id
		statuses = await self.timeout(message.author, message.guild)
		await self.warn(message, statuses, reason)
		await self.cleanup(message)

	def analyze(self, message: Message) -> Reason:
		# TEMP
		if message.author.id == ADMIN_ID and message.content == "thisisspam":
			return Reason.TESTING

		if can_bypass(message.author):
			return Reason.OK

		if message.channel.id in TRAP_CHANNEL_IDS:
			return Reason.TRAP_CHANNEL
		
		# TODO: Mr Beast

		from_user = [
			msg
			for msg in self.recent_messages
			if msg.author == message.author \
				and msg.created_at >= message.created_at - MIN_CHANNELS_DURATION
		]
		from_user.sort(key=lambda msg: msg.created_at)
		channels = {msg.channel for msg in from_user}
		duration = (message.created_at - from_user[0].created_at).total_seconds()
		if duration > 0 and len(channels) >= MAX_CHANNELS_COUNT:
			return Reason.MULTIPLE_CHANNELS_TOO_QUICK

		identical = {
			msg for msg in from_user
			if msg.content == message.content and len(msg.attachments) == len(message.attachments)
		}
		if len(identical) >= IDENTICAL_LIMIT:
			return Reason.DUPLICATE_MESSAGE

		return Reason.OK

	async def timeout(self, user: User | Member, original_guild: Guild | None) -> dict[Guild, bool]:
		# False for the guilds in which timeout failed
		statuses: dict[Guild, bool] = {}

		for member in await fetch_member_in_guilds(self, user.id):
			if member.id == ADMIN_ID and not member.guild_permissions.administrator:
				continue

			if member is not None and not member.is_timed_out():
				try:
					await member.timeout(TIMEOUT_DURATION)
					statuses[member.guild] = True
				except Exception:
					statuses[member.guild] = False
				self.logger.debug(f"Timeout in {member.guild.name}: {statuses[member.guild]}") # DEBUG

		return statuses

	async def warn(self, message: Message, statuses: dict[Guild, bool], reason: Reason):
		self.logger.info(f"Spam detected from {message.author.display_name} ({message.author.id}) in {message.channel.jump_url}")

		mutual = set(statuses)
		mutual_visible = [guild for guild in mutual if "DISCOVERABLE" in guild.features]
		if len(mutual_visible) > 5:
			mutual_visible = sample(mutual_visible, 5)
		mutual_hidden = mutual.difference(mutual_visible)
		guild_names = ", ".join(guild.name for guild in mutual_visible) or "*None*"
		if mutual_hidden and mutual_visible:
			guild_names += f" and {mutual_hidden} more"

		for guild, timeout_success in statuses.items():
			channel_id = MODERATION_CHANNELS_IDS.get(guild.id)
			channel = self.get_channel(channel_id or 0)
			if not isinstance(channel, TextChannel):
				self.logger.warn(f"{guild.name} doesn't have a correct report channel")
				continue

			embed = discord.Embed(
				title="Spam detected",
				description=message.content[:1000],
				colour=0xff0000,
				timestamp=message.created_at,
			)

			files = [
				await attachment.to_file()
				for attachment in message.attachments
			]

			embed.add_field(name="Author", value=message.author.mention + " " + message.author.name)
			embed.add_field(name="Reason", value=reason.value)
			embed.add_field(name="Channel", value=message.channel.jump_url)
			embed.add_field(name="Attached images", value=len(files))
			embed.add_field(name="Mutual servers", value=guild_names)
			embed.add_field(name="Timed out", value="Success" if timeout_success else "**FAILED !**")

			view = build_view(message)
			self.logger.debug(f"Warning {channel.guild.name}") # DEBUG
			await channel.send(embed=embed, files=files, view=view)

		# Warn admin
		if self.admin is not None:
			embed = discord.Embed(
				title="Spam detected",
				description=message.content[:1000],
				colour=0xff0000,
				timestamp=message.created_at,
			)

			files = [
				await attachment.to_file()
				for attachment in message.attachments
			]

			embed.add_field(name="Author", value=message.author.mention)
			embed.add_field(name="Reason", value=reason.value)
			embed.add_field(name="Channel", value=message.channel.jump_url)
			embed.add_field(name="Attached images", value=len(files))
			embed.add_field(name="Mutual servers", value=guild_names)

			self.logger.debug("Warning admin") # DEBUG
			await self.admin.send(embed=embed, files=files)

	async def cleanup(self, message: Message):
		failed_delete: list[str] = []

		for msg in self.recent_messages:
			if msg.author == message.author:
				try:
					msg = await msg.fetch()
					await msg.delete()
				# except NotFound:
				#     pass
				except discord.Forbidden:
					self.logger.debug(f"Failed to clean in {msg.channel}") # DEBUG
					failed_delete.append(msg.jump_url)

		if failed_delete and self.admin is not None:
			await self.admin.send("-\n".join(["Failed to delete:"] + failed_delete))



class ModeratorBanButton(discord.ui.DynamicItem[discord.ui.Button], template=r"ban_(?P<user_id>[0-9]+)"):
	def __init__(self, user_id: int) -> None:
		super().__init__(discord.ui.Button(
			label="Ban",
			style=discord.ButtonStyle.danger,
			custom_id=f"ban_{user_id}"
		))
		self.user_id = user_id

	@classmethod
	async def from_custom_id(cls, interaction: Interaction, item: discord.ui.Button, match: re.Match[str]) -> "ModeratorBanButton":
		user_id = int(match["user_id"])
		return cls(user_id)

	async def callback(self, interaction: Interaction) -> None:
		if interaction.guild is None:
			await interaction.response.send_message("Error: no guild", ephemeral=True)
			return

		guild = await interaction.client.fetch_guild(interaction.guild.id)
		member = await guild.fetch_member(interaction.user.id)
		if member is None:
			await interaction.response.send_message("Error: no member", ephemeral=True)
			return

		if not member.guild_permissions.ban_members:
			await interaction.response.send_message("You do not have the permission to do this", ephemeral=True)
			return

		member = await guild.fetch_member(self.user_id)
		if member is None:
			await interaction.response.send_message("Member not found", ephemeral=True)
			return

		if can_bypass(member):
			await interaction.response.send_message("Cannot ban this member", ephemeral=True)
			return

		try:
			await member.ban()
		except Exception:
			await interaction.response.send_message("Failed to ban this member", ephemeral=True)
			return
		else:
			# view = discord.ui.View(timeout=0)
			# view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Banned", disabled=True))
			# message = await interaction.original_response()
			# await message.edit(view=view)
			self.item.label = "Banned"
			self.item.style = discord.ButtonStyle.secondary
			self.item.disabled = True
			await interaction.response.edit_message(view=self.view)

def build_view(message: Message) -> discord.ui.View:
	view = discord.ui.View(timeout=None)
	view.add_item(ModeratorBanButton(message.author.id))
	return view



def main() -> None:
	load_dotenv()
	token = os.getenv("TOKEN")
	if token is None:
		raise ValueError("Token not provided")

	client = Antispam()

	log_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
	client.logger.addHandler(log_handler)

	client.run(token, log_handler=log_handler)

if __name__ == "__main__":
	main()
