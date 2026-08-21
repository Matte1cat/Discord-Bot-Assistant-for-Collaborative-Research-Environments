import discord
from discord import app_commands
from discord.ext import commands

from monitoring.manager import MonitoringManager
from monitoring.models import CheckStatus


class Monitoring(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        manager: MonitoringManager,
    ) -> None:
        self.bot = bot
        self.manager = manager

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


async def setup(bot: commands.Bot) -> None:
    manager = getattr(bot, "monitoring_manager", None)

    if manager is None:
        raise RuntimeError(
            "MonitoringManager is not initialized."
        )

    await bot.add_cog(
        Monitoring(
            bot=bot,
            manager=manager,
        )
    )