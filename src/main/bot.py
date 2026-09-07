"""
Defines the Discord bot lifecycle and coordinates application-level components.
"""
import logging
import aiohttp

import discord
from discord.ext import commands

from config import PROJECT_ROOT, Settings

from monitoring.manager import MonitoringManager
from monitoring.service_loader import load_services
from monitoring.exceptions import MonitoringConfigurationError
from monitoring.scheduler import MonitoringScheduler
from monitoring.state_store import MonitoringStateStore
from monitoring.service_config_store import (
    ServiceConfigStore,
)

from alerts.discord_notifier import DiscordTransitionNotifier
from runtime_config_loader import load_runtime_config, RuntimeConfigurationError

from history.base import HistoryStore
from history.file_store import FileHistoryStore
from runtime_config_store import RuntimeConfigStore, RuntimeConfigStoreError

logger = logging.getLogger(__name__)


class ThesisBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.http_session: aiohttp.ClientSession | None = None
        self.monitoring_manager = MonitoringManager()
        self.monitoring_state = MonitoringStateStore()
        self.monitoring_scheduler: MonitoringScheduler | None = None
        self.service_config_store = (
            ServiceConfigStore(
                self.settings.services_config_path
            )
        )
        self.history_store: HistoryStore | None = None
        self.runtime_config_store = (
            RuntimeConfigStore(
                self.settings.runtime_config_path
            )
        )
        self.service_management_roles: dict[
            int,
            set[int],
        ] = {}

        self.discord_alert_notifiers: dict[
            int,
            DiscordTransitionNotifier,
        ] = {}

        self.discord_alerts_active = False

        intents = discord.Intents.default()

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()

        self._register_services()

        runtime_config = load_runtime_config(
            self.settings.runtime_config_path,
            PROJECT_ROOT,
        )

        self.service_management_roles = {
            guild_config.guild_id: set(
                guild_config.authorized_role_ids
            )
            for guild_config
            in runtime_config.service_management_guilds
        }

        logger.info(
            (
                "Service management permissions loaded "
                "| authorized_roles=%d"
            ),
            len(
                self.service_management_roles
            ),
        )
        
        self.discord_alerts_active = (
            runtime_config.discord_alerts_enabled
        )

        self.discord_alert_notifiers = {}

        notifiers = ()

        if self.discord_alerts_active:
            for destination in (
                runtime_config
                .discord_alert_destinations
            ):
                notifier = DiscordTransitionNotifier(
                    bot=self,
                    destination=destination,
                )

                self.discord_alert_notifiers[
                    destination.guild_id
                ] = notifier

            notifiers = tuple(
                self.discord_alert_notifiers.values()
            )

            logger.info(
                (
                    "Discord monitoring alerts enabled "
                    "| destinations=%d"
                ),
                len(notifiers),
            )

        else:
            logger.info(
                "Discord monitoring alerts disabled."
            )

        if runtime_config.history_enabled:
            self.history_store = FileHistoryStore(
                directory=runtime_config.history_directory,
                max_file_size_bytes=(
                    runtime_config
                    .history_max_file_size_bytes
                ),
            )

            logger.info(
                "Monitoring history enabled | directory=%s",
                runtime_config.history_directory,
            )

        else:
            self.history_store = None

            logger.info(
                "Monitoring history disabled."
            )

        self.monitoring_scheduler = MonitoringScheduler(
            manager=self.monitoring_manager,
            state_store=self.monitoring_state,
            interval_seconds=(
                runtime_config.monitoring_interval_seconds
            ),
            history_store=self.history_store,
            notifiers=notifiers,
        )

        self.monitoring_scheduler.start()

        await self.load_extension("cogs.general")
        await self.load_extension("cogs.monitoring")
        await self.load_extension("cogs.service_admin")
        await self.load_extension("cogs.config_admin")

        await self._sync_application_commands()

    async def on_ready(self) -> None:
        logger.info(
            "Bot ready | user=%s | guilds=%d",
            self.user,
            len(self.guilds),
        )
        for guild in self.guilds:
            await self._ensure_guild_configuration(
                guild
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

    async def on_guild_join(
        self,
        guild: discord.Guild,
    ) -> None:
        await self._ensure_guild_configuration(
            guild
        )

    async def _ensure_guild_configuration(
        self,
        guild: discord.Guild,
    ) -> None:
        try:
            await self.runtime_config_store.ensure_guild(
                guild_id=guild.id,
                guild_name=guild.name,
            )

        except RuntimeConfigStoreError:
            logger.exception(
                (
                    "Unable to persist guild "
                    "service-management configuration"
                )
            )
            return

        self.service_management_roles.setdefault(
            guild.id,
            set(),
        )

        logger.info(
            (
                "Guild configuration available "
                "| guild=%s | guild_id=%s"
            ),
            guild.name,
            guild.id,
        )

    async def _sync_application_commands(
        self,
    ) -> None:
        if self.settings.test_guild_id is not None:
            guild = discord.Object(
                id=self.settings.test_guild_id
            )

            self.tree.copy_global_to(
                guild=guild
            )

            synced = await self.tree.sync(
                guild=guild
            )

            logger.info(
                (
                    "Synced %d application command(s) "
                    "to development guild %s"
                ),
                len(synced),
                self.settings.test_guild_id,
            )

            return

        synced = await self.tree.sync()

        logger.info(
            (
                "Synced %d global application "
                "command(s)"
            ),
            len(synced),
        )