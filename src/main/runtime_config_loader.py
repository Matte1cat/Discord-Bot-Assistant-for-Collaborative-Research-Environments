import json
from pathlib import Path

from runtime_config import (
    DiscordAlertDestination,
    RuntimeConfig,
)


class RuntimeConfigurationError(ValueError):
    """Raised when runtime configuration is invalid."""


def _parse_discord_id(
    value: object,
    field_name: str,
) -> int:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError(
            f"'{field_name}' must be a non-empty string."
        )

    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeConfigurationError(
            f"'{field_name}' must contain a valid Discord ID."
        ) from exc

    if parsed <= 0:
        raise RuntimeConfigurationError(
            f"'{field_name}' must be greater than zero."
        )

    return parsed


def load_runtime_config(
    config_path: Path,
) -> RuntimeConfig:
    try:
        with config_path.open(
            mode="r",
            encoding="utf-8",
        ) as file:
            config = json.load(file)

    except FileNotFoundError as exc:
        raise RuntimeConfigurationError(
            f"Runtime configuration file not found: {config_path}"
        ) from exc

    except json.JSONDecodeError as exc:
        raise RuntimeConfigurationError(
            f"Invalid JSON in runtime configuration: "
            f"{exc.msg} at line {exc.lineno}"
        ) from exc

    if not isinstance(config, dict):
        raise RuntimeConfigurationError(
            "Runtime configuration root must be an object."
        )

    monitoring = config.get("monitoring")

    if not isinstance(monitoring, dict):
        raise RuntimeConfigurationError(
            "'monitoring' must be an object."
        )

    interval = monitoring.get("interval_seconds")

    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or interval <= 0
    ):
        raise RuntimeConfigurationError(
            "'monitoring.interval_seconds' "
            "must be a positive number."
        )

    alerts = config.get("alerts", {})

    if not isinstance(alerts, dict):
        raise RuntimeConfigurationError(
            "'alerts' must be an object."
        )

    discord_alerts = alerts.get("discord", {})

    if not isinstance(discord_alerts, dict):
        raise RuntimeConfigurationError(
            "'alerts.discord' must be an object."
        )

    enabled = discord_alerts.get("enabled", False)

    if not isinstance(enabled, bool):
        raise RuntimeConfigurationError(
            "'alerts.discord.enabled' must be a boolean."
        )

    raw_destinations = discord_alerts.get(
        "destinations",
        [],
    )

    if not isinstance(raw_destinations, list):
        raise RuntimeConfigurationError(
            "'alerts.discord.destinations' must be a list."
        )

    destinations: list[DiscordAlertDestination] = []

    for index, raw_destination in enumerate(
        raw_destinations
    ):
        if not isinstance(raw_destination, dict):
            raise RuntimeConfigurationError(
                f"Discord destination #{index + 1} "
                "must be an object."
            )

        name = raw_destination.get("name")

        if not isinstance(name, str) or not name.strip():
            raise RuntimeConfigurationError(
                f"Discord destination #{index + 1}: "
                "'name' must be a non-empty string."
            )

        guild_id = _parse_discord_id(
            raw_destination.get("guild_id"),
            "guild_id",
        )

        channel_id = _parse_discord_id(
            raw_destination.get("channel_id"),
            "channel_id",
        )

        destinations.append(
            DiscordAlertDestination(
                name=name.strip(),
                guild_id=guild_id,
                channel_id=channel_id,
            )
        )

    if enabled and not destinations:
        raise RuntimeConfigurationError(
            "Discord alerts are enabled but "
            "no destinations are configured."
        )

    return RuntimeConfig(
        monitoring_interval_seconds=float(interval),
        discord_alerts_enabled=enabled,
        discord_alert_destinations=tuple(
            destinations
        ),
    )