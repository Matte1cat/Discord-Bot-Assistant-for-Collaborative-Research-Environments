"""
Provides safe persistent updates to the monitored services configuration.
"""

import asyncio
import json
from pathlib import Path
from typing import Any


class ServiceConfigStoreError(RuntimeError):
    pass


class ServiceConfigStore:
    def __init__(
        self,
        config_path: Path,
    ) -> None:
        self._config_path = config_path
        self._lock = asyncio.Lock()

    async def add_service(
        self,
        service_config: dict[str, Any],
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._add_service_sync,
                service_config,
            )

    async def add_check(
        self,
        service_key: str,
        check_config: dict[str, Any],
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._add_check_sync,
                service_key,
                check_config,
            )

    async def remove_service(
        self,
        service_key: str,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._remove_service_sync,
                service_key,
            )

    async def remove_check(
        self,
        service_key: str,
        check_name: str,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._remove_check_sync,
                service_key,
                check_name,
            )

    def _add_service_sync(
        self,
        service_config: dict[str, Any],
    ) -> None:
        root = self._load_root()
        services = self._get_services(root)

        service_key = service_config.get("key")

        if (
            not isinstance(service_key, str)
            or not service_key.strip()
        ):
            raise ServiceConfigStoreError(
                "Service configuration does not "
                "contain a valid key."
            )

        if any(
            isinstance(service, dict)
            and service.get("key") == service_key
            for service in services
        ):
            raise ServiceConfigStoreError(
                f"Service '{service_key}' already exists."
            )

        services.append(service_config)

        self._write_root(root)

    def _add_check_sync(
        self,
        service_key: str,
        check_config: dict[str, Any],
    ) -> None:
        root = self._load_root()
        services = self._get_services(root)

        service_config = self._find_service(
            services,
            service_key,
        )

        checks = service_config.get("checks")

        if not isinstance(checks, list):
            raise ServiceConfigStoreError(
                (
                    f"Service '{service_key}' "
                    "does not contain a valid checks list."
                )
            )

        check_name = check_config.get("name")

        if (
            not isinstance(check_name, str)
            or not check_name.strip()
        ):
            raise ServiceConfigStoreError(
                "Check configuration does not "
                "contain a valid name."
            )

        normalized_name = (
            check_name.strip().casefold()
        )

        if any(
            isinstance(check, dict)
            and isinstance(
                check.get("name"),
                str,
            )
            and check["name"].strip().casefold()
            == normalized_name
            for check in checks
        ):
            raise ServiceConfigStoreError(
                (
                    f"Check '{check_name}' already "
                    f"exists for service "
                    f"'{service_key}'."
                )
            )

        checks.append(check_config)

        self._write_root(root)

    def _remove_service_sync(
        self,
        service_key: str,
    ) -> None:
        root = self._load_root()
        services = self._get_services(root)

        service_index = next(
            (
                index
                for index, service
                in enumerate(services)
                if isinstance(service, dict)
                and service.get("key") == service_key
            ),
            None,
        )

        if service_index is None:
            raise ServiceConfigStoreError(
                f"Service '{service_key}' "
                "does not exist."
            )

        del services[service_index]

        self._write_root(root)

    def _remove_check_sync(
        self,
        service_key: str,
        check_name: str,
    ) -> None:
        root = self._load_root()
        services = self._get_services(root)

        service_config = self._find_service(
            services,
            service_key,
        )

        checks = service_config.get("checks")

        if not isinstance(checks, list):
            raise ServiceConfigStoreError(
                (
                    f"Service '{service_key}' "
                    "does not contain a valid checks list."
                )
            )

        if len(checks) <= 1:
            raise ServiceConfigStoreError(
                (
                    "The last check of a service "
                    "cannot be removed. Delete the "
                    "service instead."
                )
            )

        normalized_name = (
            check_name.strip().casefold()
        )

        check_index = next(
            (
                index
                for index, check
                in enumerate(checks)
                if isinstance(check, dict)
                and isinstance(
                    check.get("name"),
                    str,
                )
                and check["name"].strip().casefold()
                == normalized_name
            ),
            None,
        )

        if check_index is None:
            raise ServiceConfigStoreError(
                (
                    f"Check '{check_name}' does not "
                    f"exist for service "
                    f"'{service_key}'."
                )
            )

        del checks[check_index]

        self._write_root(root)

    def _load_root(
        self,
    ) -> dict[str, Any]:
        try:
            raw_content = (
                self._config_path.read_text(
                    encoding="utf-8"
                )
            )

            root = json.loads(raw_content)

        except FileNotFoundError as exc:
            raise ServiceConfigStoreError(
                "Services configuration file "
                "does not exist."
            ) from exc

        except json.JSONDecodeError as exc:
            raise ServiceConfigStoreError(
                "Services configuration file "
                "contains invalid JSON."
            ) from exc

        except OSError as exc:
            raise ServiceConfigStoreError(
                "Unable to read services "
                "configuration."
            ) from exc

        if not isinstance(root, dict):
            raise ServiceConfigStoreError(
                "Services configuration root "
                "must be an object."
            )

        return root

    @staticmethod
    def _get_services(
        root: dict[str, Any],
    ) -> list[Any]:
        services = root.get("services")

        if not isinstance(services, list):
            raise ServiceConfigStoreError(
                "'services' must be a list."
            )

        return services

    @staticmethod
    def _find_service(
        services: list[Any],
        service_key: str,
    ) -> dict[str, Any]:
        service_config = next(
            (
                service
                for service in services
                if isinstance(service, dict)
                and service.get("key") == service_key
            ),
            None,
        )

        if service_config is None:
            raise ServiceConfigStoreError(
                f"Service '{service_key}' "
                "does not exist."
            )

        return service_config

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

            raise ServiceConfigStoreError(
                "Unable to update services "
                "configuration."
            ) from exc