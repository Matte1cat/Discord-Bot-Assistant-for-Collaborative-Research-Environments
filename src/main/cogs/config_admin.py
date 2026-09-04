"""
Provides Discord commands for viewing and updating selected runtime settings.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.service_admin import (
    ServiceManagementPermissionError,
    can_manage_services,
)
from runtime_config_store import (
    RuntimeConfigStore,
    RuntimeConfigStoreError,
)


logger = logging.getLogger(__name__)


class ConfigAdmin(commands.Cog):
    config = app_commands.Group(
        name="config",
        description=(
            "View and update selected bot "
            "runtime configuration."
        ),
    )

    def __init__(
        self,
        bot: commands.Bot,
        runtime_config_store: RuntimeConfigStore,
    ) -> None:
        self.bot = bot
        self.runtime_config_store = (
            runtime_config_store
        )

    @config.command(
        name="show",
        description=(
            "Show selected persisted "
            "runtime configuration."
        ),
    )
    @can_manage_services()
    async def show_config(
        self,
        interaction: discord.Interaction,
    ) -> None:
        try:
            settings = (
                await self.runtime_config_store
                .get_editable_settings()
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "Runtime configuration could "
                    f"not be read: {exc}"
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Runtime configuration",
            description=(
                "These values are read from the "
                "persisted runtime configuration."
            ),
        )

        embed.add_field(
            name="Monitoring interval",
            value=(
                f"`"
                f"{settings['monitoring_interval_seconds']}"
                f"` seconds"
            ),
            inline=False,
        )

        embed.add_field(
            name="History",
            value=(
                "Enabled"
                if settings["history_enabled"]
                else "Disabled"
            ),
            inline=True,
        )

        embed.add_field(
            name="History directory",
            value=(
                f"`{settings['history_directory']}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Discord alerts",
            value=(
                "Enabled"
                if settings[
                    "discord_alerts_enabled"
                ]
                else "Disabled"
            ),
            inline=True,
        )

        embed.add_field(
            name="Alert destinations",
            value=str(
                settings[
                    "discord_destination_count"
                ]
            ),
            inline=True,
        )

        embed.set_footer(
            text=(
                "Configuration changes made through "
                "Discord require a bot restart "
                "to take effect."
            )
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @config.command(
        name="monitoring-interval",
        description=(
            "Change the periodic monitoring interval."
        ),
    )
    @app_commands.describe(
        seconds="Monitoring interval in seconds.",
    )
    @can_manage_services()
    async def set_monitoring_interval(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[
            int,
            1,
            86400,
        ],
    ) -> None:
        try:
            await (
                self.runtime_config_store
                .set_monitoring_interval(
                    float(seconds)
                )
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "Monitoring interval could not "
                    f"be saved: {exc}"
                ),
                ephemeral=True,
            )
            return

        logger.info(
            (
                "Monitoring interval configuration "
                "updated | seconds=%s | guild_id=%s"
            ),
            seconds,
            interaction.guild_id,
        )

        await interaction.response.send_message(
            (
                f"Monitoring interval saved as "
                f"`{seconds}` seconds.\n"
                "**Restart the bot to apply it.**"
            ),
            ephemeral=True,
        )

    @config.command(
        name="history-enabled",
        description=(
            "Enable or disable monitoring history."
        ),
    )
    @can_manage_services()
    async def set_history_enabled(
        self,
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        try:
            await (
                self.runtime_config_store
                .set_history_enabled(
                    enabled
                )
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "History configuration could "
                    f"not be saved: {exc}"
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                "Monitoring history saved as "
                f"`{'enabled' if enabled else 'disabled'}`.\n"
                "**Restart the bot to apply it.**"
            ),
            ephemeral=True,
        )

    @config.command(
        name="alerts-enabled",
        description=(
            "Enable or disable Discord "
            "transition alerts."
        ),
    )
    @can_manage_services()
    async def set_alerts_enabled(
        self,
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        try:
            await (
                self.runtime_config_store
                .set_discord_alerts_enabled(
                    enabled
                )
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "Alert configuration could "
                    f"not be saved: {exc}"
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                "Discord alerts saved as "
                f"`{'enabled' if enabled else 'disabled'}`.\n"
                "**Restart the bot to apply it.**"
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
                "You are not authorized to modify "
                "bot runtime configuration."
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


async def setup(
    bot: commands.Bot,
) -> None:
    runtime_config_store = getattr(
        bot,
        "runtime_config_store",
        None,
    )

    if runtime_config_store is None:
        raise RuntimeError(
            "RuntimeConfigStore is not initialized."
        )

    await bot.add_cog(
        ConfigAdmin(
            bot=bot,
            runtime_config_store=(
                runtime_config_store
            ),
        )
    )