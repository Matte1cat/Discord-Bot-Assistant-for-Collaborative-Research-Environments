"""
Delivers service status transition notifications to configured Discord destinations.
"""
import logging

import discord
from discord.ext import commands

from monitoring.models import (
    CheckStatus,
    ServiceTransition,
)
from runtime_config import DiscordAlertDestination

logger = logging.getLogger(__name__)


class DiscordTransitionNotifier:
    def __init__(
        self,
        bot: commands.Bot,
        destination: DiscordAlertDestination,
    ) -> None:
        self._bot = bot
        self._destination = destination

    async def notify(
        self,
        transition: ServiceTransition,
    ) -> None:
        channel = self._bot.get_partial_messageable(
            self._destination.channel_id
        )

        embed = self._build_embed(transition)

        await channel.send(embed=embed)

        logger.info(
            (
                "Discord transition alert sent | "
                "destination=%s | previous=%s | current=%s"
            ),
            self._destination.name,
            transition.previous_status.value.upper(),
            transition.current_status.value.upper(),
            extra={
                "service": transition.service_key,
                "check": "-",
            },
        )

    def _build_embed(
        self,
        transition: ServiceTransition,
    ) -> discord.Embed:
        if transition.current_status is CheckStatus.UP:
            title = "Service recovered"
            color = discord.Color.green()

        elif transition.current_status is CheckStatus.DOWN:
            title = "Service unavailable"
            color = discord.Color.red()

        else:
            title = "Monitoring error"
            color = discord.Color.orange()

        embed = discord.Embed(
            title=title,
            description=transition.service_name,
            color=color,
            timestamp=transition.detected_at,
        )

        embed.add_field(
            name="Previous status",
            value=(
                transition.previous_status
                .value
                .upper()
            ),
            inline=True,
        )

        embed.add_field(
            name="Current status",
            value=(
                transition.current_status
                .value
                .upper()
            ),
            inline=True,
        )

        for result in transition.current_result.check_results:
            response_time = (
                f"{result.response_time_ms:.0f} ms"
                if result.response_time_ms is not None
                else "N/A"
            )

            embed.add_field(
                name=result.check_name,
                value=(
                    f"Status: **"
                    f"{result.status.value.upper()}**\n"
                    f"Response time: `{response_time}`\n"
                    f"Details: `{result.message or 'N/A'}`"
                ),
                inline=False,
            )

        return embed