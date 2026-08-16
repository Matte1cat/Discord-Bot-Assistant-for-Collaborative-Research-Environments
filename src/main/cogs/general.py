import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Check whether the bot is online.",
    )
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)

        await interaction.response.send_message(
            f"Pong! {latency_ms} ms"
        )

    @app_commands.command(
        name="about",
        description="Show information about the bot.",
    )
    async def about(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Discord Bot Assistant",
            description=(
                "A modular Discord assistant for service monitoring "
                "and automation."
            ),
        )

        embed.add_field(
            name="Status",
            value="Development",
            inline=True,
        )

        embed.add_field(
            name="Version",
            value="0.1.0",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))