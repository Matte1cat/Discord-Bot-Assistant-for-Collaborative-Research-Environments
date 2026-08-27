from dataclasses import dataclass


@dataclass(frozen=True)
class DiscordAlertDestination:
    name: str
    guild_id: int
    channel_id: int


@dataclass(frozen=True)
class RuntimeConfig:
    monitoring_interval_seconds: float
    discord_alerts_enabled: bool
    discord_alert_destinations: tuple[
        DiscordAlertDestination, ...
    ]