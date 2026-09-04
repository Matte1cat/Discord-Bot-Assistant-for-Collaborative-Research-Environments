"""
Tests persistent runtime configuration updates and per-guild role management.
"""

import json

import pytest

from runtime_config_store import (
    RuntimeConfigStore,
    RuntimeConfigStoreError,
)


def write_runtime_config(
    path,
) -> None:
    path.write_text(
        json.dumps(
            {
                "monitoring": {
                    "interval_seconds": 60
                },
                "history": {
                    "enabled": True,
                    "directory": "data/history",
                },
                "service_management": {
                    "guilds": []
                },
                "alerts": {
                    "discord": {
                        "enabled": True,
                        "destinations": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_ensure_guild_adds_new_guild(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.ensure_guild(
        guild_id=111,
        guild_name="Test Guild",
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    guilds = (
        root[
            "service_management"
        ]["guilds"]
    )

    assert len(guilds) == 1

    assert guilds[0] == {
        "guild_id": "111",
        "guild_name": "Test Guild",
        "authorized_role_ids": [],
    }


@pytest.mark.asyncio
async def test_ensure_guild_is_idempotent(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.ensure_guild(
        111,
        "Old Name",
    )

    await store.ensure_guild(
        111,
        "New Name",
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    guilds = (
        root[
            "service_management"
        ]["guilds"]
    )

    assert len(guilds) == 1
    assert guilds[0]["guild_name"] == "New Name"


@pytest.mark.asyncio
async def test_add_authorized_role(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.add_authorized_role(
        guild_id=111,
        guild_name="Test Guild",
        role_id=222,
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    guild = (
        root[
            "service_management"
        ]["guilds"][0]
    )

    assert (
        guild["authorized_role_ids"]
        == ["222"]
    )


@pytest.mark.asyncio
async def test_duplicate_authorized_role_is_not_added_twice(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.add_authorized_role(
        111,
        "Test Guild",
        222,
    )

    await store.add_authorized_role(
        111,
        "Test Guild",
        222,
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    roles = (
        root[
            "service_management"
        ]["guilds"][0][
            "authorized_role_ids"
        ]
    )

    assert roles == ["222"]


@pytest.mark.asyncio
async def test_remove_authorized_role(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.add_authorized_role(
        111,
        "Test Guild",
        222,
    )

    await store.remove_authorized_role(
        guild_id=111,
        role_id=222,
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    roles = (
        root[
            "service_management"
        ]["guilds"][0][
            "authorized_role_ids"
        ]
    )

    assert roles == []


@pytest.mark.asyncio
async def test_remove_unknown_role_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.ensure_guild(
        111,
        "Test Guild",
    )

    with pytest.raises(
        RuntimeConfigStoreError,
        match="not authorized",
    ):
        await store.remove_authorized_role(
            guild_id=111,
            role_id=999,
        )


@pytest.mark.asyncio
async def test_set_monitoring_interval(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.set_monitoring_interval(
        120
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        root["monitoring"]["interval_seconds"]
        == 120
    )


@pytest.mark.asyncio
async def test_invalid_monitoring_interval_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    with pytest.raises(
        RuntimeConfigStoreError,
        match="positive",
    ):
        await store.set_monitoring_interval(
            0
        )


@pytest.mark.asyncio
async def test_set_history_enabled(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.set_history_enabled(
        False
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        root["history"]["enabled"]
        is False
    )


@pytest.mark.asyncio
async def test_set_discord_alerts_enabled(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    await store.set_discord_alerts_enabled(
        False
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        root["alerts"]["discord"]["enabled"]
        is False
    )


@pytest.mark.asyncio
async def test_get_editable_settings(
    tmp_path,
) -> None:
    path = tmp_path / "runtime.json"
    write_runtime_config(path)

    store = RuntimeConfigStore(path)

    settings = await store.get_editable_settings()

    assert (
        settings[
            "monitoring_interval_seconds"
        ]
        == 60
    )

    assert settings["history_enabled"] is True

    assert (
        settings["history_directory"]
        == "data/history"
    )

    assert (
        settings["discord_alerts_enabled"]
        is True
    )

    assert (
        settings["discord_destination_count"]
        == 0
    )