from urllib.parse import urlparse

import aiohttp

from monitoring.checks.base import BaseCheck
from monitoring.checks.http_check import HTTPCheck
from monitoring.exceptions import MonitoringConfigurationError


def _require_string(
    config: dict,
    field: str,
) -> str:
    value = config.get(field)

    if not isinstance(value, str) or not value.strip():
        raise MonitoringConfigurationError(
            f"'{field}' must be a non-empty string."
        )

    return value.strip()


def build_check(
    config: dict,
    http_session: aiohttp.ClientSession,
) -> BaseCheck:
    if not isinstance(config, dict):
        raise MonitoringConfigurationError(
            "Each check must be an object."
        )

    check_type = _require_string(
        config,
        "type",
    ).lower()

    if check_type == "http":
        name = _require_string(config, "name")
        url = _require_string(config, "url")

        parsed_url = urlparse(url)

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise MonitoringConfigurationError(
                f"Invalid HTTP URL: '{url}'"
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
                "'timeout_seconds' must be a positive number."
            )

        return HTTPCheck(
            name=name,
            url=url,
            session=http_session,
            expected_status=expected_status,
            timeout_seconds=float(timeout_seconds),
        )

    raise MonitoringConfigurationError(
        f"Unsupported check type: '{check_type}'"
    )