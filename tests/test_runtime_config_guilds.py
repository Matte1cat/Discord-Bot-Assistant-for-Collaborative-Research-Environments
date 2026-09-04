"""
Tests loading and validation of per-guild service-management configuration.
"""

import json

import pytest

from runtime_config_loader import (
    RuntimeConfigurationError,
    load_runtime_config,
)


def make_config(
    guilds,
) -> dict:
    return {
        "monitoring": {
            "interval_seconds": 60,
        },
        "history": {
            "enabled": True,
            "directory": "data/history",
        },
        "service_management": {
            "guilds": guilds,
        },
        "alerts": {
            "discord": {
                "enabled": False,
                "destinations": [],
            }
        },
    }


def write_config(
    path,
    config,
) -> None:
    path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )


def test_load_multiple_service_management_guilds(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"

    write_config(
        path,
        make_config(
            [
                {
                    "guild_id": "111",
                    "guild_name": "Guild A",
                    "authorized_role_ids": [
                        "10",
                        "20",
                    ],
                },
                {
                    "guild_id": "222",
                    "guild_name": "Guild B",
                    "authorized_role_ids": [
                        "30",
                    ],
                },
            ]
        ),
    )

    config = load_runtime_config(
        path,
        project_root=tmp_path,
    )

    assert (
        len(
            config.service_management_guilds
        )
        == 2
    )

    first = (
        config.service_management_guilds[0]
    )

    second = (
        config.service_management_guilds[1]
    )

    assert first.guild_id == 111
    assert first.guild_name == "Guild A"

    assert (
        first.authorized_role_ids
        == (10, 20)
    )

    assert second.guild_id == 222

    assert (
        second.authorized_role_ids
        == (30,)
    )


def test_duplicate_role_ids_are_removed(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"

    write_config(
        path,
        make_config(
            [
                {
                    "guild_id": "111",
                    "guild_name": "Guild A",
                    "authorized_role_ids": [
                        "10",
                        "10",
                        "20",
                    ],
                }
            ]
        ),
    )

    config = load_runtime_config(
        path,
        project_root=tmp_path,
    )

    assert (
        config
        .service_management_guilds[0]
        .authorized_role_ids
        == (10, 20)
    )


def test_invalid_guild_id_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"

    write_config(
        path,
        make_config(
            [
                {
                    "guild_id": "banana",
                    "guild_name": "Guild A",
                    "authorized_role_ids": [],
                }
            ]
        ),
    )

    with pytest.raises(
        RuntimeConfigurationError,
        match="invalid guild ID",
    ):
        load_runtime_config(
            path,
            project_root=tmp_path,
        )


def test_invalid_role_id_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"

    write_config(
        path,
        make_config(
            [
                {
                    "guild_id": "111",
                    "guild_name": "Guild A",
                    "authorized_role_ids": [
                        "banana"
                    ],
                }
            ]
        ),
    )

    with pytest.raises(
        RuntimeConfigurationError,
        match="not a valid Discord ID",
    ):
        load_runtime_config(
            path,
            project_root=tmp_path,
        )


def test_missing_service_management_defaults_to_empty(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"

    config = make_config(
        []
    )

    del config["service_management"]

    write_config(
        path,
        config,
    )

    loaded = load_runtime_config(
        path,
        project_root=tmp_path,
    )

    assert (
        loaded.service_management_guilds
        == ()
    )