"""
Provides safe persistent updates to mutable runtime configuration.
"""

import asyncio
import json
from pathlib import Path
from typing import Any


class RuntimeConfigStoreError(RuntimeError):
    pass


class RuntimeConfigStore:
    def __init__(
        self,
        config_path: Path,
    ) -> None:
        self._config_path = config_path
        self._lock = asyncio.Lock()

    async def ensure_guild(
        self,
        guild_id: int,
        guild_name: str,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._ensure_guild_sync,
                guild_id,
                guild_name,
            )

    async def add_authorized_role(
        self,
        guild_id: int,
        guild_name: str,
        role_id: int,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._add_authorized_role_sync,
                guild_id,
                guild_name,
                role_id,
            )

    async def remove_authorized_role(
        self,
        guild_id: int,
        role_id: int,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._remove_authorized_role_sync,
                guild_id,
                role_id,
            )

    def _ensure_guild_sync(
        self,
        guild_id: int,
        guild_name: str,
    ) -> None:
        root = self._load_root()
        guilds = self._get_guilds(root)

        guild_config = self._find_guild(
            guilds,
            guild_id,
        )

        changed = False

        if guild_config is None:
            guilds.append(
                {
                    "guild_id": str(guild_id),
                    "guild_name": guild_name,
                    "authorized_role_ids": [],
                }
            )

            changed = True

        elif guild_config.get(
            "guild_name"
        ) != guild_name:
            guild_config["guild_name"] = guild_name
            changed = True

        if changed:
            self._write_root(root)

    def _add_authorized_role_sync(
        self,
        guild_id: int,
        guild_name: str,
        role_id: int,
    ) -> None:
        root = self._load_root()
        guilds = self._get_guilds(root)

        guild_config = self._find_guild(
            guilds,
            guild_id,
        )

        if guild_config is None:
            guild_config = {
                "guild_id": str(guild_id),
                "guild_name": guild_name,
                "authorized_role_ids": [],
            }

            guilds.append(
                guild_config
            )

        role_ids = guild_config.get(
            "authorized_role_ids"
        )

        if not isinstance(
            role_ids,
            list,
        ):
            raise RuntimeConfigStoreError(
                "Guild authorized_role_ids must be a list."
            )

        string_role_id = str(role_id)

        if string_role_id not in role_ids:
            role_ids.append(
                string_role_id
            )

        guild_config["guild_name"] = (
            guild_name
        )

        self._write_root(root)

    def _remove_authorized_role_sync(
        self,
        guild_id: int,
        role_id: int,
    ) -> None:
        root = self._load_root()
        guilds = self._get_guilds(root)

        guild_config = self._find_guild(
            guilds,
            guild_id,
        )

        if guild_config is None:
            raise RuntimeConfigStoreError(
                f"Guild '{guild_id}' is not configured."
            )

        role_ids = guild_config.get(
            "authorized_role_ids"
        )

        if not isinstance(
            role_ids,
            list,
        ):
            raise RuntimeConfigStoreError(
                "Guild authorized_role_ids must be a list."
            )

        string_role_id = str(role_id)

        if string_role_id not in role_ids:
            raise RuntimeConfigStoreError(
                f"Role '{role_id}' is not authorized."
            )

        role_ids.remove(
            string_role_id
        )

        self._write_root(root)

    def _load_root(
        self,
    ) -> dict[str, Any]:
        try:
            text = self._config_path.read_text(
                encoding="utf-8"
            )

            root = json.loads(text)

        except FileNotFoundError as exc:
            raise RuntimeConfigStoreError(
                "Runtime configuration file does not exist."
            ) from exc

        except json.JSONDecodeError as exc:
            raise RuntimeConfigStoreError(
                "Runtime configuration contains invalid JSON."
            ) from exc

        except OSError as exc:
            raise RuntimeConfigStoreError(
                "Unable to read runtime configuration."
            ) from exc

        if not isinstance(
            root,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "Runtime configuration root must be an object."
            )

        return root

    @staticmethod
    def _get_guilds(
        root: dict[str, Any],
    ) -> list[Any]:
        management = root.setdefault(
            "service_management",
            {},
        )

        if not isinstance(
            management,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "'service_management' must be an object."
            )

        guilds = management.setdefault(
            "guilds",
            [],
        )

        if not isinstance(
            guilds,
            list,
        ):
            raise RuntimeConfigStoreError(
                "'service_management.guilds' must be a list."
            )

        return guilds

    @staticmethod
    def _find_guild(
        guilds: list[Any],
        guild_id: int,
    ) -> dict[str, Any] | None:
        expected_id = str(
            guild_id
        )

        return next(
            (
                guild
                for guild in guilds
                if isinstance(
                    guild,
                    dict,
                )
                and str(
                    guild.get(
                        "guild_id",
                        ""
                    )
                ) == expected_id
            ),
            None,
        )

    def _write_root(
        self,
        root: dict[str, Any],
    ) -> None:
        serialized = json.dumps(
            root,
            indent=2,
            ensure_ascii=False,
        )

        temporary_path = (
            self._config_path.with_name(
                f".{self._config_path.name}.tmp"
            )
        )

        try:
            temporary_path.write_text(
                serialized + "\n",
                encoding="utf-8",
            )

            temporary_path.replace(
                self._config_path
            )

        except OSError as exc:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise RuntimeConfigStoreError(
                "Unable to update runtime configuration."
            ) from exc

    async def get_editable_settings(
        self,
    ) -> dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(
                self._get_editable_settings_sync
            )


    async def set_monitoring_interval(
        self,
        interval_seconds: float,
    ) -> None:
        if interval_seconds <= 0:
            raise RuntimeConfigStoreError(
                "Monitoring interval must be positive."
            )

        async with self._lock:
            await asyncio.to_thread(
                self._set_monitoring_interval_sync,
                interval_seconds,
            )


    async def set_history_enabled(
        self,
        enabled: bool,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._set_history_enabled_sync,
                enabled,
            )


    async def set_discord_alerts_enabled(
        self,
        enabled: bool,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._set_discord_alerts_enabled_sync,
                enabled,
            )

    def _get_editable_settings_sync(
        self,
    ) -> dict[str, Any]:
        root = self._load_root()

        monitoring = root.get(
            "monitoring",
            {},
        )

        history = root.get(
            "history",
            {},
        )

        alerts = root.get(
            "alerts",
            {},
        )

        if not isinstance(monitoring, dict):
            raise RuntimeConfigStoreError(
                "'monitoring' must be an object."
            )

        if not isinstance(history, dict):
            raise RuntimeConfigStoreError(
                "'history' must be an object."
            )

        if not isinstance(alerts, dict):
            raise RuntimeConfigStoreError(
                "'alerts' must be an object."
            )

        discord_alerts = alerts.get(
            "discord",
            {},
        )

        if not isinstance(
            discord_alerts,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "'alerts.discord' must be an object."
            )

        destinations = discord_alerts.get(
            "destinations",
            [],
        )

        if not isinstance(
            destinations,
            list,
        ):
            raise RuntimeConfigStoreError(
                (
                    "'alerts.discord.destinations' "
                    "must be a list."
                )
            )

        return {
            "monitoring_interval_seconds": (
                monitoring.get(
                    "interval_seconds"
                )
            ),
            "history_enabled": history.get(
                "enabled",
                True,
            ),
            "history_directory": history.get(
                "directory",
                "data/history",
            ),
            "discord_alerts_enabled": (
                discord_alerts.get(
                    "enabled",
                    False,
                )
            ),
            "discord_destination_count": len(
                destinations
            ),
        }


    def _set_monitoring_interval_sync(
        self,
        interval_seconds: float,
    ) -> None:
        root = self._load_root()

        monitoring = root.setdefault(
            "monitoring",
            {},
        )

        if not isinstance(
            monitoring,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "'monitoring' must be an object."
            )

        monitoring["interval_seconds"] = (
            interval_seconds
        )

        self._write_root(
            root
        )


    def _set_history_enabled_sync(
        self,
        enabled: bool,
    ) -> None:
        root = self._load_root()

        history = root.setdefault(
            "history",
            {},
        )

        if not isinstance(
            history,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "'history' must be an object."
            )

        history["enabled"] = enabled

        self._write_root(
            root
        )


    def _set_discord_alerts_enabled_sync(
        self,
        enabled: bool,
    ) -> None:
        root = self._load_root()

        alerts = root.setdefault(
            "alerts",
            {},
        )

        if not isinstance(
            alerts,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "'alerts' must be an object."
            )

        discord_alerts = alerts.setdefault(
            "discord",
            {},
        )

        if not isinstance(
            discord_alerts,
            dict,
        ):
            raise RuntimeConfigStoreError(
                "'alerts.discord' must be an object."
            )

        discord_alerts["enabled"] = enabled

        self._write_root(
            root
        )