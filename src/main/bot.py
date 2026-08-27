import logging
import aiohttp

import discord
from discord.ext import commands

from config import Settings

from monitoring.manager import MonitoringManager
from monitoring.service_loader import load_services
from monitoring.exceptions import MonitoringConfigurationError
from monitoring.scheduler import MonitoringScheduler
from monitoring.state_store import MonitoringStateStore

from alerts.discord_notifier import DiscordTransitionNotifier
from runtime_config_loader import load_runtime_config

logger = logging.getLogger(__name__)


class ThesisBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.http_session: aiohttp.ClientSession | None = None
        self.monitoring_manager = MonitoringManager()
        self.monitoring_state = MonitoringStateStore()
        self.monitoring_scheduler: MonitoringScheduler | None = None

        intents = discord.Intents.default()

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()

        self._register_services()

        runtime_config = load_runtime_config(
            self.settings.runtime_config_path
        )

        notifiers = ()

        if runtime_config.discord_alerts_enabled:
            notifiers = tuple(
                DiscordTransitionNotifier(
                    bot=self,
                    destination=destination,
                )
                for destination
                in runtime_config.discord_alert_destinations
            )

            logger.info(
                "Discord monitoring alerts enabled | destinations=%d",
                len(notifiers),
            )

        else:
            logger.info(
                "Discord monitoring alerts disabled."
            )

        self.monitoring_scheduler = MonitoringScheduler(
            manager=self.monitoring_manager,
            state_store=self.monitoring_state,
            interval_seconds=(
                runtime_config.monitoring_interval_seconds
            ),
            notifiers=notifiers,
        )

        self.monitoring_scheduler.start()

        await self.load_extension("cogs.general")
        await self.load_extension("cogs.monitoring")

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

    def _register_services(self) -> None:
        if self.http_session is None:
            raise RuntimeError(
                "HTTP session is not initialized."
            )

        try:
            services = load_services(
                self.settings.services_config_path,
                self.http_session,
            )

        except MonitoringConfigurationError as exc:
            logger.critical(
                "Invalid monitoring configuration: %s",
                exc,
            )
            raise

        for service in services:
            self.monitoring_manager.register(service)

        logger.info(
            "Registered %d monitoring service(s)",
            len(services),
        )

    async def close(self) -> None:
        if self.monitoring_scheduler is not None:
            await self.monitoring_scheduler.stop()

        if (
            self.http_session is not None
            and not self.http_session.closed
        ):
            await self.http_session.close()
            logger.info("HTTP session closed")

        await super().close()