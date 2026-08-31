"""
Loads and validates monitored services from the external service configuration.
"""
import json
from pathlib import Path

import aiohttp

from monitoring.checks.factory import build_check
from monitoring.service import Service
from monitoring.exceptions import MonitoringConfigurationError


def _require_string(
    config: dict,
    field: str,
    context: str,
) -> str:
    value = config.get(field)

    if not isinstance(value, str) or not value.strip():
        raise MonitoringConfigurationError(
            f"{context}: '{field}' must be a non-empty string."
        )

    return value.strip()

def load_services(
    config_path: Path,
    http_session: aiohttp.ClientSession,
) -> tuple[Service, ...]:

    try:
        with config_path.open(
            mode="r",
            encoding="utf-8",
        ) as file:
            config = json.load(file)

    except FileNotFoundError as exc:
        raise MonitoringConfigurationError(
            f"Service configuration file not found: "
            f"{config_path}"
        ) from exc

    except json.JSONDecodeError as exc:
        raise MonitoringConfigurationError(
            f"Invalid JSON in service configuration: "
            f"{exc.msg} at line {exc.lineno}"
        ) from exc

    if not isinstance(config, dict):
        raise MonitoringConfigurationError(
            "Service configuration root must be an object."
        )

    raw_services = config.get("services")

    if not isinstance(raw_services, list):
        raise MonitoringConfigurationError(
            "Service configuration must contain a 'services' list."
        )

    services: list[Service] = []
    registered_keys: set[str] = set()

    for index, raw_service in enumerate(raw_services):
        context = f"Service #{index + 1}"

        if not isinstance(raw_service, dict):
            raise MonitoringConfigurationError(
                f"{context} must be an object."
            )

        key = _require_string(
            raw_service,
            "key",
            context,
        )

        display_name = _require_string(
            raw_service,
            "display_name",
            context,
        )

        if key in registered_keys:
            raise MonitoringConfigurationError(
                f"Duplicate service key: '{key}'"
            )

        raw_checks = raw_service.get("checks")

        if (
            not isinstance(raw_checks, list)
            or not raw_checks
        ):
            raise MonitoringConfigurationError(
                f"Service '{key}' must contain "
                "at least one check."
            )

        checks = []

        for check_index, check_config in enumerate(raw_checks):
            try:
                check = build_check(
                    check_config,
                    http_session,
                )

            except MonitoringConfigurationError as exc:
                raise MonitoringConfigurationError(
                    f"Service '{key}', check "
                    f"#{check_index + 1}: {exc}"
                ) from exc

            checks.append(check)

        services.append(
            Service(
                key=key,
                display_name=display_name,
                checks=tuple(checks),
            )
        )

        registered_keys.add(key)

    return tuple(services)