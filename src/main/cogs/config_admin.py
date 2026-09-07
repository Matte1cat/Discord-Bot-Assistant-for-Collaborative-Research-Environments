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
from alerts.discord_notifier import (
    DiscordTransitionNotifier,
)

from runtime_config import (
    DiscordAlertDestination,
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
            alert_channel_id = (
                await self.runtime_config_store
                .get_alert_destination(
                    interaction.guild_id
                )
                if interaction.guild_id is not None
                else None
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

        embed.add_field(
            name="Alert channel for this server",
            value=(
                f"<#{alert_channel_id}>"
                if alert_channel_id is not None
                else "Not configured"
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                "Alert-channel changes are applied live. "
                "Other runtime setting changes may "
                "require a bot restart."
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

    def _apply_alert_destination_live(
        self,
        destination: DiscordAlertDestination,
    ) -> bool:
        if not getattr(
            self.bot,
            "discord_alerts_active",
            False,
        ):
            return False

        scheduler = getattr(
            self.bot,
            "monitoring_scheduler",
            None,
        )

        notifiers = getattr(
            self.bot,
            "discord_alert_notifiers",
            None,
        )

        if scheduler is None or notifiers is None:
            raise RuntimeError(
                (
                    "Discord alert runtime "
                    "is not initialized."
                )
            )

        existing = notifiers.get(
            destination.guild_id
        )

        if existing is not None:
            existing.update_destination(
                destination
            )
            return True

        notifier = DiscordTransitionNotifier(
            bot=self.bot,
            destination=destination,
        )

        notifiers[
            destination.guild_id
        ] = notifier

        scheduler.add_notifier(
            notifier
        )

        return True


    def _remove_alert_destination_live(
        self,
        guild_id: int,
    ) -> None:
        scheduler = getattr(
            self.bot,
            "monitoring_scheduler",
            None,
        )

        notifiers = getattr(
            self.bot,
            "discord_alert_notifiers",
            None,
        )

        if scheduler is None or notifiers is None:
            raise RuntimeError(
                (
                    "Discord alert runtime "
                    "is not initialized."
                )
            )

        notifier = notifiers.pop(
            guild_id,
            None,
        )

        if notifier is not None:
            scheduler.remove_notifier(
                notifier
            )

    @config.command(
        name="alert-channel",
        description=(
            "Set the alert channel for this server."
        ),
    )
    @app_commands.describe(
        channel=(
            "Channel that will receive "
            "monitoring transition alerts."
        ),
    )
    @can_manage_services()
    async def set_alert_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                (
                    "This command can only be "
                    "used in a server."
                ),
                ephemeral=True,
            )
            return

        if channel.guild.id != interaction.guild.id:
            await interaction.response.send_message(
                (
                    "The alert channel must belong "
                    "to this server."
                ),
                ephemeral=True,
            )
            return

        try:
            await (
                self.runtime_config_store
                .set_alert_destination(
                    guild_id=interaction.guild.id,
                    guild_name=interaction.guild.name,
                    channel_id=channel.id,
                )
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "Alert channel could not "
                    f"be saved: {exc}"
                ),
                ephemeral=True,
            )
            return

        destination = DiscordAlertDestination(
            name=interaction.guild.name,
            guild_id=interaction.guild.id,
            channel_id=channel.id,
        )

        try:
            applied_live = (
                self._apply_alert_destination_live(
                    destination
                )
            )

        except Exception:
            logger.exception(
                (
                    "Alert channel persisted but "
                    "live update failed "
                    "| guild_id=%s | channel_id=%s"
                ),
                interaction.guild.id,
                channel.id,
            )

            await interaction.response.send_message(
                (
                    f"Alert channel saved as "
                    f"{channel.mention}, but the live "
                    "update failed.\n"
                    "**Restart the bot to apply it.**"
                ),
                ephemeral=True,
            )
            return

        logger.info(
            (
                "Discord alert channel configured "
                "| guild_id=%s | channel_id=%s"
            ),
            interaction.guild.id,
            channel.id,
        )

        if applied_live:
            message = (
                f"Alert channel set to "
                f"{channel.mention} and applied "
                "**immediately**."
            )

        else:
            message = (
                f"Alert channel saved as "
                f"{channel.mention}.\n"
                "Discord alerts are not currently "
                "active; the channel will be used "
                "when alerts are enabled and the "
                "bot is restarted."
            )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    @config.command(
        name="alert-channel-clear",
        description=(
            "Remove the alert channel "
            "configured for this server."
        ),
    )
    @can_manage_services()
    async def clear_alert_channel(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                (
                    "This command can only be "
                    "used in a server."
                ),
                ephemeral=True,
            )
            return

        try:
            alerts_disabled = (
                await self.runtime_config_store
                .remove_alert_destination(
                    guild_id=interaction.guild.id
                )
            )

        except RuntimeConfigStoreError as exc:
            await interaction.response.send_message(
                (
                    "Alert channel could not "
                    f"be removed: {exc}"
                ),
                ephemeral=True,
            )
            return

        try:
            self._remove_alert_destination_live(
                interaction.guild.id
            )

            if alerts_disabled:
                setattr(
                    self.bot,
                    "discord_alerts_active",
                    False,
                )

        except Exception:
            logger.exception(
                (
                    "Alert channel removed from "
                    "configuration but live cleanup "
                    "failed | guild_id=%s"
                ),
                interaction.guild.id,
            )

            await interaction.response.send_message(
                (
                    "Alert channel was removed from "
                    "the persisted configuration, "
                    "but the live update failed.\n"
                    "**Restart the bot to fully apply it.**"
                ),
                ephemeral=True,
            )
            return

        logger.info(
            (
                "Discord alert channel removed "
                "| guild_id=%s"
            ),
            interaction.guild.id,
        )

        if alerts_disabled:
            message = (
                "Alert channel removed. "
                "No destinations remain, so "
                "Discord alerts were also disabled."
            )
        else:
            message = (
                "Alert channel removed and "
                "applied immediately."
            )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )


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