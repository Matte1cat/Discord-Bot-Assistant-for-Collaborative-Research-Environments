"""
Provides Discord administration commands for dynamically managing monitored services.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from monitoring.checks.factory import (
    available_check_types,
    build_check,
)
from monitoring.exceptions import (
    MonitoringConfigurationError,
)
from monitoring.manager import MonitoringManager
from monitoring.service import Service
from monitoring.service_config_store import (
    ServiceConfigStore,
    ServiceConfigStoreError,
)
from monitoring.state_store import (
    MonitoringStateStore,
)
from runtime_config_store import (
    RuntimeConfigStore,
    RuntimeConfigStoreError,
)

class ServiceManagementPermissionError(
    app_commands.CheckFailure
):
    pass

def can_manage_services():
    async def predicate(
        interaction: discord.Interaction,
    ) -> bool:
        if (
            interaction.guild is None
            or not isinstance(
                interaction.user,
                discord.Member,
            )
        ):
            raise (
                ServiceManagementPermissionError(
                    "Service management commands "
                    "can only be used in a server."
                )
            )

        # Server administrators always have access.
        if (
            interaction.permissions
            .administrator
        ):
            return True

        authorized_roles = (
            getattr(
                interaction.client,
                "service_management_roles",
                {},
            ).get(
                interaction.guild.id,
                set(),
            )
        )

        member_roles = {
            role.id
            for role
            in interaction.user.roles
        }

        if (
            authorized_roles
            & member_roles
        ):
            return True

        raise ServiceManagementPermissionError(
            (
                "You are not authorized to "
                "manage monitored services."
            )
        )

    return app_commands.check(
        predicate
    )


logger = logging.getLogger(__name__)


SERVICE_KEY_PATTERN = re.compile(
    r"^[a-z0-9_-]+$"
)


DISCORD_CONFIGURABLE_CHECK_TYPES = {
    "http",
}


CheckSubmitHandler = Callable[
    [
        discord.Interaction,
        dict[str, Any],
    ],
    Awaitable[None],
]


def configurable_check_types() -> tuple[str, ...]:
    return tuple(
        check_type
        for check_type in available_check_types()
        if check_type
        in DISCORD_CONFIGURABLE_CHECK_TYPES
    )


class HTTPCheckModal(discord.ui.Modal):
    def __init__(
        self,
        title: str,
        submit_handler: CheckSubmitHandler,
    ) -> None:
        super().__init__(
            title=title
        )

        self._submit_handler = submit_handler

        self.check_name = discord.ui.TextInput(
            label="Check name",
            default="HTTP availability",
            max_length=100,
        )

        self.url = discord.ui.TextInput(
            label="URL",
            placeholder="https://example.com/",
            max_length=500,
        )

        self.expected_status = discord.ui.TextInput(
            label="Expected HTTP status",
            default="200",
            max_length=3,
        )

        self.timeout_seconds = discord.ui.TextInput(
            label="Timeout in seconds",
            default="5",
            max_length=10,
        )

        self.add_item(
            self.check_name
        )

        self.add_item(
            self.url
        )

        self.add_item(
            self.expected_status
        )

        self.add_item(
            self.timeout_seconds
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        try:
            expected_status = int(
                self.expected_status.value
            )

            timeout_seconds = float(
                self.timeout_seconds.value
            )

        except ValueError:
            await interaction.response.send_message(
                (
                    "Expected status must be an integer "
                    "and timeout must be a number."
                ),
                ephemeral=True,
            )
            return

        check_config = {
            "type": "http",
            "name": (
                self.check_name.value.strip()
            ),
            "url": (
                self.url.value.strip()
            ),
            "expected_status": expected_status,
            "timeout_seconds": timeout_seconds,
        }

        await self._submit_handler(
            interaction,
            check_config,
        )


class ServiceAdmin(commands.Cog):
    service = app_commands.Group(
        name="service",
        description=(
            "Manage monitored services."
        ),
    )

    def __init__(
        self,
        bot: commands.Bot,
        manager: MonitoringManager,
        config_store: ServiceConfigStore,
        state_store: MonitoringStateStore,
        http_session: aiohttp.ClientSession,
        runtime_config_store: RuntimeConfigStore,
    ) -> None:
        self.bot = bot
        self.manager = manager
        self.config_store = config_store
        self.state_store = state_store
        self.http_session = http_session
        self.runtime_config_store = runtime_config_store

    @service.command(
        name="add",
        description=(
            "Add a new monitored service."
        ),
    )
    @app_commands.describe(
        key=(
            "Unique service identifier, "
            "for example 'unimore'."
        ),
        display_name=(
            "Human-readable service name."
        ),
        check_type=(
            "Type of initial monitoring check."
        ),
    )
    @can_manage_services()
    async def add_service(
        self,
        interaction: discord.Interaction,
        key: str,
        display_name: str,
        check_type: str,
    ) -> None:
        normalized_key = (
            key.strip().lower()
        )

        normalized_name = (
            display_name.strip()
        )

        normalized_check_type = (
            check_type.strip().lower()
        )

        if not normalized_key:
            await interaction.response.send_message(
                "Service key cannot be empty.",
                ephemeral=True,
            )
            return

        if not SERVICE_KEY_PATTERN.fullmatch(
            normalized_key
        ):
            await interaction.response.send_message(
                (
                    "Service key may contain only "
                    "lowercase letters, numbers, "
                    "hyphens and underscores."
                ),
                ephemeral=True,
            )
            return

        if not normalized_name:
            await interaction.response.send_message(
                "Display name cannot be empty.",
                ephemeral=True,
            )
            return

        if (
            self.manager.get_service(
                normalized_key
            )
            is not None
        ):
            await interaction.response.send_message(
                (
                    f"Service `{normalized_key}` "
                    "already exists."
                ),
                ephemeral=True,
            )
            return

        if (
            normalized_check_type
            not in configurable_check_types()
        ):
            await interaction.response.send_message(
                (
                    "Unsupported or currently "
                    "non-configurable check type: "
                    f"`{normalized_check_type}`"
                ),
                ephemeral=True,
            )
            return

        if normalized_check_type == "http":

            async def submit_handler(
                modal_interaction: (
                    discord.Interaction
                ),
                check_config: dict[str, Any],
            ) -> None:
                await self.create_service(
                    interaction=modal_interaction,
                    service_key=normalized_key,
                    display_name=normalized_name,
                    check_config=check_config,
                )

            await interaction.response.send_modal(
                HTTPCheckModal(
                    title="Configure initial HTTP check",
                    submit_handler=submit_handler,
                )
            )

    @service.command(
        name="check-add",
        description=(
            "Add a monitoring check "
            "to an existing service."
        ),
    )
    @app_commands.describe(
        service=(
            "Service that should receive "
            "the new check."
        ),
        check_type=(
            "Type of monitoring check."
        ),
    )
    @can_manage_services()
    async def add_check(
        self,
        interaction: discord.Interaction,
        service: str,
        check_type: str,
    ) -> None:
        normalized_service = (
            service.strip().lower()
        )

        normalized_check_type = (
            check_type.strip().lower()
        )

        target = self.manager.get_service(
            normalized_service
        )

        if target is None:
            await interaction.response.send_message(
                (
                    f"Unknown service: "
                    f"`{normalized_service}`"
                ),
                ephemeral=True,
            )
            return

        if (
            normalized_check_type
            not in configurable_check_types()
        ):
            await interaction.response.send_message(
                (
                    "Unsupported or currently "
                    "non-configurable check type: "
                    f"`{normalized_check_type}`"
                ),
                ephemeral=True,
            )
            return

        if normalized_check_type == "http":

            async def submit_handler(
                modal_interaction: (
                    discord.Interaction
                ),
                check_config: dict[str, Any],
            ) -> None:
                await self.add_check_to_service(
                    interaction=modal_interaction,
                    service_key=normalized_service,
                    check_config=check_config,
                )

            await interaction.response.send_modal(
                HTTPCheckModal(
                    title="Configure HTTP check",
                    submit_handler=submit_handler,
                )
            )

    @add_service.autocomplete(
        "check_type"
    )
    async def add_service_check_type_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        return self._check_type_choices(
            current
        )

    @add_check.autocomplete(
        "check_type"
    )
    async def add_check_type_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        return self._check_type_choices(
            current
        )

    @add_check.autocomplete(
        "service"
    )
    async def add_check_service_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        return self._service_choices(
            current
        )

    def _check_type_choices(
        self,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        normalized_current = (
            current.casefold()
        )

        return [
            app_commands.Choice(
                name=check_type.upper(),
                value=check_type,
            )
            for check_type
            in configurable_check_types()
            if normalized_current
            in check_type.casefold()
        ][:25]

    async def create_service(
        self,
        interaction: discord.Interaction,
        service_key: str,
        display_name: str,
        check_config: dict[str, Any],
    ) -> None:
        if (
            self.manager.get_service(
                service_key
            )
            is not None
        ):
            await interaction.response.send_message(
                (
                    f"Service `{service_key}` "
                    "already exists."
                ),
                ephemeral=True,
            )
            return

        try:
            check = build_check(
                check_config,
                self.http_session,
            )

            service = Service(
                key=service_key,
                display_name=display_name,
                checks=(check,),
            )

        except MonitoringConfigurationError as exc:
            await interaction.response.send_message(
                (
                    "Invalid check configuration: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        service_config = {
            "key": service_key,
            "display_name": display_name,
            "checks": [
                check_config
            ],
        }

        try:
            await self.config_store.add_service(
                service_config
            )

        except ServiceConfigStoreError as exc:
            logger.warning(
                (
                    "Unable to persist new service "
                    "| error=%s"
                ),
                exc,
                extra={
                    "service": service_key,
                    "check": "-",
                },
            )

            await interaction.response.send_message(
                (
                    "The service could not be saved: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        try:
            self.manager.register(
                service
            )

        except Exception:
            logger.exception(
                (
                    "Service was persisted but could "
                    "not be activated at runtime"
                ),
                extra={
                    "service": service_key,
                    "check": "-",
                },
            )

            await interaction.response.send_message(
                (
                    f"Service `{service_key}` was saved, "
                    "but could not be activated live. "
                    "Restart the bot to load it."
                ),
                ephemeral=True,
            )
            return

        logger.info(
            (
                "Service added dynamically "
                "| display_name=%s"
            ),
            display_name,
            extra={
                "service": service_key,
                "check": "-",
            },
        )

        await interaction.response.send_message(
            (
                f"Service `{service_key}` added "
                "successfully and activated immediately."
            ),
            ephemeral=True,
        )

    async def add_check_to_service(
        self,
        interaction: discord.Interaction,
        service_key: str,
        check_config: dict[str, Any],
    ) -> None:
        current_service = (
            self.manager.get_service(
                service_key
            )
        )

        if current_service is None:
            await interaction.response.send_message(
                (
                    f"Service `{service_key}` "
                    "no longer exists."
                ),
                ephemeral=True,
            )
            return

        try:
            new_check = build_check(
                check_config,
                self.http_session,
            )

        except MonitoringConfigurationError as exc:
            await interaction.response.send_message(
                (
                    "Invalid check configuration: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        if any(
            existing_check.name.casefold()
            == new_check.name.casefold()
            for existing_check
            in current_service.checks
        ):
            await interaction.response.send_message(
                (
                    f"A check named "
                    f"`{new_check.name}` already exists "
                    f"for service `{service_key}`."
                ),
                ephemeral=True,
            )
            return

        try:
            await self.config_store.add_check(
                service_key=service_key,
                check_config=check_config,
            )

        except ServiceConfigStoreError as exc:
            logger.warning(
                (
                    "Unable to persist new check "
                    "| error=%s"
                ),
                exc,
                extra={
                    "service": service_key,
                    "check": new_check.name,
                },
            )

            await interaction.response.send_message(
                (
                    "The check could not be saved: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        # Retrieve it again after the asynchronous
        # persistence operation, in case the service
        # was updated while we were waiting.
        latest_service = (
            self.manager.get_service(
                service_key
            )
        )

        if latest_service is None:
            logger.error(
                (
                    "Check was persisted but service "
                    "is no longer available at runtime"
                ),
                extra={
                    "service": service_key,
                    "check": new_check.name,
                },
            )

            await interaction.response.send_message(
                (
                    f"Check `{new_check.name}` was saved, "
                    "but the service is not currently "
                    "available. Restart the bot to "
                    "reload the configuration."
                ),
                ephemeral=True,
            )
            return

        replacement = Service(
            key=latest_service.key,
            display_name=(
                latest_service.display_name
            ),
            checks=(
                latest_service.checks
                + (new_check,)
            ),
        )

        try:
            self.manager.replace(
                replacement
            )

        except Exception:
            logger.exception(
                (
                    "Check was persisted but could "
                    "not be activated at runtime"
                ),
                extra={
                    "service": service_key,
                    "check": new_check.name,
                },
            )

            await interaction.response.send_message(
                (
                    f"Check `{new_check.name}` was saved, "
                    "but could not be activated live. "
                    "Restart the bot to load it."
                ),
                ephemeral=True,
            )
            return

        logger.info(
            "Check added dynamically",
            extra={
                "service": service_key,
                "check": new_check.name,
            },
        )

        await interaction.response.send_message(
            (
                f"Check `{new_check.name}` added to "
                f"`{service_key}` and activated "
                "immediately."
            ),
            ephemeral=True,
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(
            error,
            ServiceManagementPermissionError,
        ):
            message = (
                "You are not authorized to manage "
                "monitored services. An Administrator "
                "or an authorized service-management "
                "role is required."
            )

            if interaction.response.is_done():
                await interaction.followup.send(
                    message,
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

            return

        raise error

    @service.command(
        name="list",
        description="List all configured monitored services.",
    )
    async def list_services(
        self,
        interaction: discord.Interaction,
    ) -> None:
        services = self.manager.list_services()

        if not services:
            await interaction.response.send_message(
                "No monitored services are configured.",
                ephemeral=True,
            )
            return

        embeds: list[discord.Embed] = []

        for start in range(
            0,
            len(services),
            25,
        ):
            page = services[
                start:start + 25
            ]

            embed = discord.Embed(
                title="Monitored services",
                description=(
                    f"{len(services)} configured "
                    "service(s)."
                ),
            )

            for monitored_service in page:
                value = self._format_service_checks(
                    monitored_service
                )

                embed.add_field(
                    name=(
                        f"{monitored_service.display_name} "
                        f"(`{monitored_service.key}`)"
                    ),
                    value=value,
                    inline=False,
                )

            embeds.append(embed)

        await interaction.response.send_message(
            embed=embeds[0],
            ephemeral=True,
        )

        for embed in embeds[1:]:
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )

    @staticmethod
    def _format_service_checks(
        service: Service,
    ) -> str:
        lines: list[str] = []

        for index, check in enumerate(
            service.checks
        ):
            line = (
                f"• `{check.name}` "
                f"— {type(check).__name__}"
            )

            candidate = "\n".join(
                lines + [line]
            )

            if len(candidate) > 900:
                remaining = (
                    len(service.checks) - index
                )

                lines.append(
                    f"• ... and {remaining} more"
                )
                break

            lines.append(line)

        return "\n".join(lines)

    @service.command(
        name="check-types",
        description=(
            "List all monitoring check types "
            "supported by the bot."
        ),
    )
    async def list_check_types(
        self,
        interaction: discord.Interaction,
    ) -> None:
        check_types = available_check_types()

        if not check_types:
            await interaction.response.send_message(
                "No monitoring check types are registered.",
                ephemeral=True,
            )
            return

        configurable = set(
            configurable_check_types()
        )

        lines = []

        for check_type in check_types:
            if check_type in configurable:
                availability = (
                    "configurable from Discord"
                )
            else:
                availability = (
                    "supported by core only"
                )

            lines.append(
                f"• `{check_type}` — {availability}"
            )

        embed = discord.Embed(
            title="Supported monitoring checks",
            description="\n".join(lines),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @service.command(
        name="delete",
        description="Delete a monitored service.",
    )
    @app_commands.describe(
        service="Service to delete.",
    )
    @can_manage_services()
    async def delete_service(
        self,
        interaction: discord.Interaction,
        service: str,
    ) -> None:
        service_key = (
            service.strip().lower()
        )

        current_service = (
            self.manager.get_service(
                service_key
            )
        )

        if current_service is None:
            await interaction.response.send_message(
                (
                    f"Unknown service: "
                    f"`{service_key}`"
                ),
                ephemeral=True,
            )
            return

        try:
            await self.config_store.remove_service(
                service_key
            )

        except ServiceConfigStoreError as exc:
            logger.warning(
                (
                    "Unable to persist service deletion "
                    "| error=%s"
                ),
                exc,
                extra={
                    "service": service_key,
                    "check": "-",
                },
            )

            await interaction.response.send_message(
                (
                    "The service could not be deleted: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        try:
            self.manager.unregister(
                service_key
            )

            self.state_store.remove(
                service_key
            )

        except Exception:
            logger.exception(
                (
                    "Service was removed from configuration "
                    "but could not be fully deactivated "
                    "at runtime"
                ),
                extra={
                    "service": service_key,
                    "check": "-",
                },
            )

            await interaction.response.send_message(
                (
                    f"Service `{service_key}` was removed "
                    "from configuration, but runtime "
                    "cleanup failed. Restart the bot "
                    "to ensure the change is applied."
                ),
                ephemeral=True,
            )
            return

        logger.info(
            "Service deleted dynamically",
            extra={
                "service": service_key,
                "check": "-",
            },
        )

        await interaction.response.send_message(
            (
                f"Service `{service_key}` deleted "
                "and deactivated immediately."
            ),
            ephemeral=True,
        )

    @delete_service.autocomplete(
        "service"
    )
    async def delete_service_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        return self._service_choices(
            current
        )

    def _service_choices(
        self,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        normalized_current = (
            current.casefold()
        )

        return [
            app_commands.Choice(
                name=service.display_name,
                value=service.key,
            )
            for service
            in self.manager.list_services()
            if (
                normalized_current
                in service.key.casefold()
                or normalized_current
                in service.display_name.casefold()
            )
        ][:25]

    @service.command(
        name="check-delete",
        description=(
            "Delete a monitoring check "
            "from an existing service."
        ),
    )
    @app_commands.describe(
        service="Service containing the check.",
        check="Check to delete.",
    )
    @can_manage_services()
    async def delete_check(
        self,
        interaction: discord.Interaction,
        service: str,
        check: str,
    ) -> None:
        service_key = (
            service.strip().lower()
        )

        check_name = (
            check.strip()
        )

        current_service = (
            self.manager.get_service(
                service_key
            )
        )

        if current_service is None:
            await interaction.response.send_message(
                (
                    f"Unknown service: "
                    f"`{service_key}`"
                ),
                ephemeral=True,
            )
            return

        if len(current_service.checks) <= 1:
            await interaction.response.send_message(
                (
                    "The last check of a service "
                    "cannot be removed. Delete the "
                    "service instead."
                ),
                ephemeral=True,
            )
            return

        matching_check = next(
            (
                existing_check
                for existing_check
                in current_service.checks
                if existing_check.name.casefold()
                == check_name.casefold()
            ),
            None,
        )

        if matching_check is None:
            await interaction.response.send_message(
                (
                    f"Unknown check `{check_name}` "
                    f"for service `{service_key}`."
                ),
                ephemeral=True,
            )
            return

        try:
            await self.config_store.remove_check(
                service_key=service_key,
                check_name=matching_check.name,
            )

        except ServiceConfigStoreError as exc:
            logger.warning(
                (
                    "Unable to persist check deletion "
                    "| error=%s"
                ),
                exc,
                extra={
                    "service": service_key,
                    "check": matching_check.name,
                },
            )

            await interaction.response.send_message(
                (
                    "The check could not be deleted: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        latest_service = (
            self.manager.get_service(
                service_key
            )
        )

        if latest_service is None:
            await interaction.response.send_message(
                (
                    "The check was removed from the "
                    "configuration, but the service is "
                    "no longer available at runtime. "
                    "Restart the bot to reload it."
                ),
                ephemeral=True,
            )
            return

        remaining_checks = tuple(
            existing_check
            for existing_check
            in latest_service.checks
            if existing_check.name.casefold()
            != matching_check.name.casefold()
        )

        if not remaining_checks:
            logger.error(
                (
                    "Check deletion would leave "
                    "service without checks"
                ),
                extra={
                    "service": service_key,
                    "check": matching_check.name,
                },
            )

            await interaction.response.send_message(
                (
                    "The configuration was updated, "
                    "but the runtime service could not "
                    "be updated safely. Restart the bot."
                ),
                ephemeral=True,
            )
            return

        replacement = Service(
            key=latest_service.key,
            display_name=(
                latest_service.display_name
            ),
            checks=remaining_checks,
        )

        try:
            self.manager.replace(
                replacement
            )

        except Exception:
            logger.exception(
                (
                    "Check was removed from configuration "
                    "but could not be removed at runtime"
                ),
                extra={
                    "service": service_key,
                    "check": matching_check.name,
                },
            )

            await interaction.response.send_message(
                (
                    f"Check `{matching_check.name}` "
                    "was removed from configuration, "
                    "but could not be removed live. "
                    "Restart the bot."
                ),
                ephemeral=True,
            )
            return

        logger.info(
            "Check deleted dynamically",
            extra={
                "service": service_key,
                "check": matching_check.name,
            },
        )

        await interaction.response.send_message(
            (
                f"Check `{matching_check.name}` removed "
                f"from `{service_key}` and deactivated "
                "immediately."
            ),
            ephemeral=True,
        )

    @delete_check.autocomplete(
        "service"
    )
    async def delete_check_service_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        return self._service_choices(
            current
        )

    @delete_check.autocomplete(
        "check"
    )
    async def delete_check_check_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[
        app_commands.Choice[str]
    ]:
        selected_service = (
            interaction.namespace.service
        )

        if not isinstance(
            selected_service,
            str,
        ):
            return []

        service = self.manager.get_service(
            selected_service
        )

        if service is None:
            return []

        normalized_current = (
            current.casefold()
        )

        return [
            app_commands.Choice(
                name=check.name,
                value=check.name,
            )
            for check in service.checks
            if normalized_current
            in check.name.casefold()
        ][:25]

    @service.command(
        name="manager-role-add",
        description=(
            "Authorize a Discord role "
            "to manage monitored services."
        ),
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def manager_role_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                (
                    "The @everyone role cannot be used "
                    "as a service-management role."
                ),
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                (
                    "Managed integration or bot roles "
                    "cannot be used."
                ),
                ephemeral=True,
            )
            return

        try:
            await (
                self.runtime_config_store
                .add_authorized_role(
                    guild_id=interaction.guild.id,
                    guild_name=interaction.guild.name,
                    role_id=role.id,
                )
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "The role could not be saved: "
                    f"{exc}"
                ),
                ephemeral=True,
            )
            return

        roles = (
            self.bot.service_management_roles
            .setdefault(
                interaction.guild.id,
                set(),
            )
        )

        roles.add(
            role.id
        )

        await interaction.response.send_message(
            (
                f"{role.mention} can now manage "
                "monitored services."
            ),
            ephemeral=True,
        )

    @service.command(
        name="manager-role-list",
        description=(
            "List roles authorized to manage "
            "monitored services in this server."
        ),
    )
    async def manager_role_list(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        role_ids = (
            self.bot.service_management_roles.get(
                interaction.guild.id,
                set(),
            )
        )

        if not role_ids:
            await interaction.response.send_message(
                (
                    "No service-management roles are "
                    "configured for this server. "
                    "Administrators can still manage services."
                ),
                ephemeral=True,
            )
            return

        lines: list[str] = []

        for role_id in sorted(
            role_ids
        ):
            role = interaction.guild.get_role(
                role_id
            )

            if role is None:
                lines.append(
                    (
                        f"• Deleted or unavailable role "
                        f"(`{role_id}`)"
                    )
                )
            else:
                lines.append(
                    f"• {role.mention}"
                )

        embed = discord.Embed(
            title="Service-management roles",
            description="\n".join(lines),
        )

        embed.set_footer(
            text=(
                "Server Administrators are always authorized."
            )
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @service.command(
        name="manager-role-delete",
        description=(
            "Remove a Discord role from "
            "service-management permissions."
        ),
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def manager_role_delete(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        authorized_roles = (
            self.bot.service_management_roles.get(
                interaction.guild.id,
                set(),
            )
        )

        if role.id not in authorized_roles:
            await interaction.response.send_message(
                (
                    f"{role.mention} is not currently "
                    "authorized to manage services."
                ),
                ephemeral=True,
            )
            return

        try:
            await (
                self.runtime_config_store
                .remove_authorized_role(
                    guild_id=interaction.guild.id,
                    role_id=role.id,
                )
            )

        except RuntimeConfigStoreError as exc:
            logger.warning(
                (
                    "Unable to remove service-management "
                    "role | guild_id=%s | role_id=%s "
                    "| error=%s"
                ),
                interaction.guild.id,
                role.id,
                exc,
            )

            await interaction.response.send_message(
                (
                    "The role permission could not "
                    f"be removed: {exc}"
                ),
                ephemeral=True,
            )
            return

        authorized_roles.discard(
            role.id
        )

        logger.info(
            (
                "Service-management role removed "
                "| guild_id=%s | role_id=%s"
            ),
            interaction.guild.id,
            role.id,
        )

        await interaction.response.send_message(
            (
                f"{role.mention} can no longer manage "
                "monitored services."
            ),
            ephemeral=True,
        )


async def setup(
    bot: commands.Bot,
) -> None:
    manager = getattr(
        bot,
        "monitoring_manager",
        None,
    )

    config_store = getattr(
        bot,
        "service_config_store",
        None,
    )

    http_session = getattr(
        bot,
        "http_session",
        None,
    )

    state_store = getattr(
        bot,
        "monitoring_state",
        None,
    )

    runtime_config_store = getattr(
        bot,
        "runtime_config_store",
        None,
    )

    if manager is None:
        raise RuntimeError(
            "MonitoringManager is not initialized."
        )

    if config_store is None:
        raise RuntimeError(
            "ServiceConfigStore is not initialized."
        )

    if http_session is None:
        raise RuntimeError(
            "HTTP session is not initialized."
        )

    if state_store is None:
        raise RuntimeError(
            "Monitoring state is not initialized."
        )

    if runtime_config_store is None:
        raise RuntimeError(
            "RuntimeConfigStore is not initialized."
        )

    await bot.add_cog(
        ServiceAdmin(
            bot=bot,
            manager=manager,
            config_store=config_store,
            http_session=http_session,
            state_store=state_store,
            runtime_config_store=runtime_config_store,
        )
    )