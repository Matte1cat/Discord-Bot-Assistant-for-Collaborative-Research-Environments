import discord
from discord import app_commands
from discord.ext import commands

from monitoring.manager import MonitoringManager
from monitoring.models import CheckStatus

from history.base import HistoryStore


class Monitoring(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        manager: MonitoringManager,
        history_store: HistoryStore,
    ) -> None:
        self.bot = bot
        self.manager = manager
        self.history_store = history_store

    async def service_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        current = current.casefold()

        return [
            app_commands.Choice(
                name=service.display_name,
                value=service.key,
            )
            for service in self.manager.list_services()
            if (
                current in service.key.casefold()
                or current in service.display_name.casefold()
            )
        ][:25]

    @app_commands.command(
        name="status",
        description="Check the current status of a monitored service.",
    )
    @app_commands.describe(
        service="Service to check.",
    )
    @app_commands.autocomplete(
        service=service_autocomplete,
    )
    async def status(
        self,
        interaction: discord.Interaction,
        service: str,
    ) -> None:
        target = self.manager.get_service(service)

        if target is None:
            await interaction.response.send_message(
                f"Unknown service: `{service}`",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        result = await self.manager.check_service(service)

        if result.status is CheckStatus.UP:
            color = discord.Color.green()

        elif result.status is CheckStatus.DOWN:
            color = discord.Color.red()

        else:
            color = discord.Color.orange()

        embed = discord.Embed(
            title=result.service_name,
            description=(
                f"Overall status: "
                f"**{result.status.value.upper()}**"
            ),
            color=color,
        )

        for check_result in result.check_results:
            response_time = (
                f"{check_result.response_time_ms:.0f} ms"
                if check_result.response_time_ms is not None
                else "N/A"
            )

            checked_at = discord.utils.format_dt(
                check_result.checked_at,
                style="R",
            )

            embed.add_field(
                name=check_result.check_name,
                value=(
                    f"Status: **"
                    f"{check_result.status.value.upper()}**\n"
                    f"Response time: `{response_time}`\n"
                    f"Details: `{check_result.message}`\n"
                    f"Checked: {checked_at}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="history",
        description="Show recent monitoring history for a service.",
    )
    @app_commands.describe(
        service="Service whose history should be shown.",
        limit="Number of recent monitoring results to show.",
    )
    @app_commands.autocomplete(
        service=service_autocomplete,
    )
    async def history(
        self,
        interaction: discord.Interaction,
        service: str,
        limit: app_commands.Range[int, 1, 10] = 5,
    ) -> None:
        target = self.manager.get_service(service)

        if target is None:
            await interaction.response.send_message(
                f"Unknown service: `{service}`",
                ephemeral=True,
            )
            return

        if self.history_store is None:
            await interaction.response.send_message(
                "Monitoring history is disabled.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            thinking=True
        )

        results = (
            await self.history_store
            .get_recent_service_results(
                service_key=service,
                limit=limit,
            )
        )

        transitions = (
            await self.history_store
            .get_recent_transitions(
                service_key=service,
                limit=limit,
            )
        )

        embed = discord.Embed(
            title=f"Monitoring history — {target.display_name}",
            description=(
                "Automatic monitoring results only."
            ),
        )

        if not results:
            embed.add_field(
                name="Results",
                value="No monitoring history available.",
                inline=False,
            )

        for result in results:
            recorded_at = discord.utils.format_dt(
                result.recorded_at,
                style="R",
            )

            check_lines = []

            for check in result.check_results:
                response_time = (
                    f"{check.response_time_ms:.0f} ms"
                    if check.response_time_ms is not None
                    else "N/A"
                )

                check_lines.append(
                    (
                        f"**{check.check_name}** — "
                        f"{check.status.value.upper()}\n"
                        f"`{response_time}` — "
                        f"{check.message or 'N/A'}"
                    )
                )

            embed.add_field(
                name=(
                    f"{result.status.value.upper()} "
                    f"• {recorded_at}"
                ),
                value="\n".join(check_lines),
                inline=False,
            )

        if transitions:
            transition_lines = []

            for transition in transitions:
                detected_at = discord.utils.format_dt(
                    transition.detected_at,
                    style="R",
                )

                transition_lines.append(
                    (
                        f"{detected_at}: "
                        f"**"
                        f"{transition.previous_status.value.upper()}"
                        f" → "
                        f"{transition.current_status.value.upper()}"
                        f"**"
                    )
                )

            embed.add_field(
                name="Recent transitions",
                value="\n".join(
                    transition_lines
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                "Manual /status checks are not stored "
                "in monitoring history."
            )
        )

        await interaction.followup.send(
            embed=embed
        )


async def setup(
    bot: commands.Bot,
) -> None:
    manager = getattr(
        bot,
        "monitoring_manager",
        None,
    )

    if manager is None:
        raise RuntimeError(
            "MonitoringManager is not initialized."
        )

    history_store = getattr(
        bot,
        "history_store",
        None,
    )

    await bot.add_cog(
        Monitoring(
            bot=bot,
            manager=manager,
            history_store=history_store,
        )
    )