"""
Builds monitoring checks from validated external configuration definitions.
"""

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import aiohttp

from monitoring.checks.base import BaseCheck
from monitoring.checks.http_check import HTTPCheck
from monitoring.exceptions import MonitoringConfigurationError


CheckBuilder = Callable[
    [dict[str, Any], aiohttp.ClientSession],
    BaseCheck,
]


def _require_non_empty_string(
    config: dict[str, Any],
    field_name: str,
) -> str:
    value = config.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise MonitoringConfigurationError(
            f"'{field_name}' must be a non-empty string."
        )

    return value.strip()


def _build_http_check(
    config: dict[str, Any],
    http_session: aiohttp.ClientSession,
) -> BaseCheck:
    name = _require_non_empty_string(
        config,
        "name",
    )

    url = _require_non_empty_string(
        config,
        "url",
    )

    parsed_url = urlparse(url)

    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
    ):
        raise MonitoringConfigurationError(
            f"Invalid HTTP URL: {url}"
        )

    expected_status = config.get(
        "expected_status",
        200,
    )

    if (
        isinstance(expected_status, bool)
        or not isinstance(expected_status, int)
        or not 100 <= expected_status <= 599
    ):
        raise MonitoringConfigurationError(
            "'expected_status' must be an integer "
            "between 100 and 599."
        )

    timeout_seconds = config.get(
        "timeout_seconds",
        5.0,
    )

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(
            timeout_seconds,
            (int, float),
        )
        or timeout_seconds <= 0
    ):
        raise MonitoringConfigurationError(
            "'timeout_seconds' must be "
            "a positive number."
        )

    return HTTPCheck(
        name=name,
        url=url,
        session=http_session,
        expected_status=expected_status,
        timeout_seconds=float(timeout_seconds),
    )


_CHECK_BUILDERS: dict[str, CheckBuilder] = {
    "http": _build_http_check,
}


def available_check_types() -> tuple[str, ...]:
    return tuple(
        sorted(_CHECK_BUILDERS)
    )


def build_check(
    config: dict[str, Any],
    http_session: aiohttp.ClientSession,
) -> BaseCheck:
    if not isinstance(config, dict):
        raise MonitoringConfigurationError(
            "Check configuration must be an object."
        )

    check_type = _require_non_empty_string(
        config,
        "type",
    ).lower()

    builder = _CHECK_BUILDERS.get(
        check_type
    )

    if builder is None:
        raise MonitoringConfigurationError(
            f"Unsupported check type: {check_type}"
        )

    return builder(
        config,
        http_session,
    )