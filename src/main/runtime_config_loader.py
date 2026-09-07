"""
Loads and validates runtime behaviour from the external JSON configuration.
"""
import json
from pathlib import Path

from runtime_config import (
    DiscordAlertDestination,
    RuntimeConfig,
    ServiceManagementGuildConfig,
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
    project_root: Path,
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

    history = config.get("history", {})

    if not isinstance(history, dict):
        raise RuntimeConfigurationError(
            "'history' must be an object."
        )

    history_enabled = history.get(
        "enabled",
        True,
    )

    if not isinstance(history_enabled, bool):
        raise RuntimeConfigurationError(
            "'history.enabled' must be a boolean."
        )

    raw_history_directory = history.get(
        "directory",
        "data/history",
    )

    if (
        not isinstance(raw_history_directory, str)
        or not raw_history_directory.strip()
    ):
        raise RuntimeConfigurationError(
            "'history.directory' must be "
            "a non-empty string."
        )

    history_directory = Path(
        raw_history_directory
    )

    if not history_directory.is_absolute():
        history_directory = (
            project_root / history_directory
        )

    history_directory = history_directory.resolve()

    history_max_file_size_mb = history.get(
        "max_file_size_mb",
        25,
    )

    if (
        isinstance(
            history_max_file_size_mb,
            bool,
        )
        or not isinstance(
            history_max_file_size_mb,
            int,
        )
        or history_max_file_size_mb <= 0
    ):
        raise RuntimeConfigurationError(
            (
                "'history.max_file_size_mb' "
                "must be a positive integer."
            )
        )

    history_max_file_size_bytes = (
        history_max_file_size_mb
        * 1024
        * 1024
    )

    service_management = config.get(
        "service_management",
        {},
    )

    if not isinstance(
        service_management,
        dict,
    ):
        raise RuntimeConfigurationError(
            "'service_management' must be an object."
        )

    raw_guilds = service_management.get(
        "guilds",
        [],
    )

    if not isinstance(
        raw_guilds,
        list,
    ):
        raise RuntimeConfigurationError(
            "'service_management.guilds' must be a list."
        )

    service_management_guilds: list[
        ServiceManagementGuildConfig
    ] = []

    for guild_index, raw_guild in enumerate(
        raw_guilds
    ):
        if not isinstance(
            raw_guild,
            dict,
        ):
            raise RuntimeConfigurationError(
                (
                    "Service-management guild at index "
                    f"{guild_index} must be an object."
                )
            )

        raw_guild_id = raw_guild.get(
            "guild_id"
        )

        try:
            guild_id = int(
                raw_guild_id
            )

        except (TypeError, ValueError) as exc:
            raise RuntimeConfigurationError(
                (
                    "Service-management guild at index "
                    f"{guild_index} has an invalid guild ID."
                )
            ) from exc

        if guild_id <= 0:
            raise RuntimeConfigurationError(
                (
                    "Service-management guild at index "
                    f"{guild_index} must have a positive "
                    "guild ID."
                )
            )

        guild_name = raw_guild.get(
            "guild_name",
            "",
        )

        if not isinstance(
            guild_name,
            str,
        ):
            raise RuntimeConfigurationError(
                (
                    "Service-management guild at index "
                    f"{guild_index} has an invalid guild name."
                )
            )

        raw_role_ids = raw_guild.get(
            "authorized_role_ids",
            [],
        )

        if not isinstance(
            raw_role_ids,
            list,
        ):
            raise RuntimeConfigurationError(
                (
                    "Service-management guild at index "
                    f"{guild_index} must contain an "
                    "'authorized_role_ids' list."
                )
            )

        authorized_role_ids: list[int] = []

        for role_index, raw_role_id in enumerate(
            raw_role_ids
        ):
            if isinstance(
                raw_role_id,
                bool,
            ):
                raise RuntimeConfigurationError(
                    (
                        "Authorized role at index "
                        f"{role_index} for guild "
                        f"'{guild_id}' is not a valid "
                        "Discord ID."
                    )
                )

            try:
                role_id = int(
                    raw_role_id
                )

            except (TypeError, ValueError) as exc:
                raise RuntimeConfigurationError(
                    (
                        "Authorized role at index "
                        f"{role_index} for guild "
                        f"'{guild_id}' is not a valid "
                        "Discord ID."
                    )
                ) from exc

            if role_id <= 0:
                raise RuntimeConfigurationError(
                    (
                        "Authorized role IDs must "
                        "be positive."
                    )
                )

            authorized_role_ids.append(
                role_id
            )

        service_management_guilds.append(
            ServiceManagementGuildConfig(
                guild_id=guild_id,
                guild_name=guild_name,
                authorized_role_ids=tuple(
                    dict.fromkeys(
                        authorized_role_ids
                    )
                ),
            )
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

    destination_guild_ids: set[int] = set()

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

        if guild_id in destination_guild_ids:
            raise RuntimeConfigurationError(
                (
                    "Only one Discord alert destination "
                    "may be configured per guild."
                )
            )

        destination_guild_ids.add(
            guild_id
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
        service_management_guilds=tuple(
            service_management_guilds
        ),
        monitoring_interval_seconds=float(interval),
        history_enabled=history_enabled,
        history_directory=history_directory,
        discord_alerts_enabled=enabled,
        history_max_file_size_bytes=(
            history_max_file_size_bytes
        ),
        discord_alert_destinations=tuple(
            destinations
        ),
    )