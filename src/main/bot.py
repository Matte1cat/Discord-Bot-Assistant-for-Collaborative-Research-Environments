import logging

import discord
from discord.ext import commands

from config import Settings


logger = logging.getLogger(__name__)


class ThesisBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        intents = discord.Intents.default()

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.general")

        if self.settings.test_guild_id is None:
            logger.warning(
                "No test guild configured. Command sync skipped."
            )
            return

        guild = discord.Object(
            id=self.settings.test_guild_id
        )

        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)

        logger.info(
            "Synced %d command(s) to test guild %s",
            len(synced),
            self.settings.test_guild_id,
        )

    async def on_ready(self) -> None:
        logger.info(
            "Logged in as %s (ID: %s)",
            self.user,
            self.user.id if self.user else "unknown",
        )