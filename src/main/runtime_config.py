"""
Defines the runtime configuration models for monitoring, history, and alerts.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscordAlertDestination:
    name: str
    guild_id: int
    channel_id: int


@dataclass(frozen=True)
class RuntimeConfig:
    monitoring_interval_seconds: float

    history_enabled: bool
    history_directory: Path

    discord_alerts_enabled: bool
    discord_alert_destinations: tuple[
        DiscordAlertDestination, ...
    ]