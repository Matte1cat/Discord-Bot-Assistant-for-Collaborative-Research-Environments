"""
Tests loading and validation of monitoring, history, and Discord runtime configuration.
"""
import json

import pytest

from runtime_config_loader import (
    RuntimeConfigurationError,
    load_runtime_config,
)


def test_valid_runtime_configuration_with_multiple_destinations(
    tmp_path,
) -> None:
    config_path = tmp_path / "runtime.json"

    config = {
        "monitoring": {
            "interval_seconds": 60,
        },
        "alerts": {
            "discord": {
                "enabled": True,
                "destinations": [
                    {
                        "name": "server-a",
                        "guild_id": "111111111111111111",
                        "channel_id": "222222222222222222",
                    },
                    {
                        "name": "server-b",
                        "guild_id": "333333333333333333",
                        "channel_id": "444444444444444444",
                    },
                ],
            }
        },
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    runtime_config = load_runtime_config(
        config_path,
        project_root=tmp_path,
    )

    assert (
        runtime_config.monitoring_interval_seconds
        == 60.0
    )

    assert (
        runtime_config.discord_alerts_enabled
        is True
    )

    assert (
        len(
            runtime_config.discord_alert_destinations
        )
        == 2
    )

    first = (
        runtime_config
        .discord_alert_destinations[0]
    )

    second = (
        runtime_config
        .discord_alert_destinations[1]
    )

    assert first.name == "server-a"
    assert first.guild_id == 111111111111111111
    assert first.channel_id == 222222222222222222

    assert second.name == "server-b"
    assert second.guild_id == 333333333333333333
    assert second.channel_id == 444444444444444444


def test_discord_alerts_can_be_disabled_without_destinations(
    tmp_path,
) -> None:
    config_path = tmp_path / "runtime.json"

    config = {
        "monitoring": {
            "interval_seconds": 60,
        },
        "alerts": {
            "discord": {
                "enabled": False,
                "destinations": [],
            }
        },
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    runtime_config = load_runtime_config(
        config_path,
        project_root=tmp_path,
    )

    assert (
        runtime_config.discord_alerts_enabled
        is False
    )

    assert (
        runtime_config.discord_alert_destinations
        == ()
    )


def test_enabled_discord_alerts_require_destination(
    tmp_path,
) -> None:
    config_path = tmp_path / "runtime.json"

    config = {
        "monitoring": {
            "interval_seconds": 60,
        },
        "alerts": {
            "discord": {
                "enabled": True,
                "destinations": [],
            }
        },
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeConfigurationError,
        match="no destinations",
    ):
        load_runtime_config(
            config_path,
            project_root=tmp_path,
        )


@pytest.mark.parametrize(
    "invalid_interval",
    [
        0,
        -1,
        -100,
        True,
        "sixty",
    ],
)
def test_invalid_monitoring_interval_is_rejected(
    tmp_path,
    invalid_interval,
) -> None:
    config_path = tmp_path / "runtime.json"

    config = {
        "monitoring": {
            "interval_seconds": invalid_interval,
        },
        "alerts": {
            "discord": {
                "enabled": False,
                "destinations": [],
            }
        },
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeConfigurationError,
        match="positive number",
    ):
        load_runtime_config(
            config_path,
            project_root=tmp_path,
        )


def test_invalid_discord_channel_id_is_rejected(
    tmp_path,
) -> None:
    config_path = tmp_path / "runtime.json"

    config = {
        "monitoring": {
            "interval_seconds": 60,
        },
        "alerts": {
            "discord": {
                "enabled": True,
                "destinations": [
                    {
                        "name": "test-server",
                        "guild_id": "111111111111111111",
                        "channel_id": "this-is-not-an-id",
                    }
                ],
            }
        },
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeConfigurationError,
        match="valid Discord ID",
    ):
        load_runtime_config(
            config_path,
            project_root=tmp_path,
        )


def test_invalid_discord_guild_id_is_rejected(
    tmp_path,
) -> None:
    config_path = tmp_path / "runtime.json"

    config = {
        "monitoring": {
            "interval_seconds": 60,
        },
        "alerts": {
            "discord": {
                "enabled": True,
                "destinations": [
                    {
                        "name": "test-server",
                        "guild_id": "banana",
                        "channel_id": "222222222222222222",
                    }
                ],
            }
        },
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeConfigurationError,
        match="valid Discord ID",
    ):
        load_runtime_config(
            config_path,
            project_root=tmp_path,
        )