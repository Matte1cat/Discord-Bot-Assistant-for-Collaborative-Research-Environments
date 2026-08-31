"""
Tests loading and validation of monitored services and their configured checks.
"""
import json
from typing import cast

import aiohttp
import pytest

from monitoring.checks.http_check import HTTPCheck
from monitoring.exceptions import MonitoringConfigurationError
from monitoring.service_loader import load_services


def fake_http_session() -> aiohttp.ClientSession:
    return cast(
        aiohttp.ClientSession,
        object(),
    )


def test_load_valid_http_service(tmp_path) -> None:
    config_path = tmp_path / "services.json"

    config = {
        "services": [
            {
                "key": "test",
                "display_name": "Test Service",
                "checks": [
                    {
                        "type": "http",
                        "name": "HTTP availability",
                        "url": "https://example.com",
                        "expected_status": 200,
                        "timeout_seconds": 5.0,
                    }
                ],
            }
        ]
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    services = load_services(
        config_path,
        fake_http_session(),
    )

    assert len(services) == 1

    service = services[0]

    assert service.key == "test"
    assert service.display_name == "Test Service"
    assert len(service.checks) == 1
    assert isinstance(
        service.checks[0],
        HTTPCheck,
    )


def test_duplicate_service_key_is_rejected(tmp_path) -> None:
    config_path = tmp_path / "services.json"

    config = {
        "services": [
            {
                "key": "same",
                "display_name": "First Service",
                "checks": [
                    {
                        "type": "http",
                        "name": "check-a",
                        "url": "https://example.com",
                    }
                ],
            },
            {
                "key": "same",
                "display_name": "Second Service",
                "checks": [
                    {
                        "type": "http",
                        "name": "check-b",
                        "url": "https://example.com",
                    }
                ],
            },
        ]
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        MonitoringConfigurationError,
        match="Duplicate service key",
    ):
        load_services(
            config_path,
            fake_http_session(),
        )


def test_unknown_check_type_is_rejected(tmp_path) -> None:
    config_path = tmp_path / "services.json"

    config = {
        "services": [
            {
                "key": "test",
                "display_name": "Test Service",
                "checks": [
                    {
                        "type": "banana",
                        "name": "Completely legitimate banana check",
                    }
                ],
            }
        ]
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        MonitoringConfigurationError,
        match="Unsupported check type",
    ):
        load_services(
            config_path,
            fake_http_session(),
        )


def test_invalid_json_is_rejected(tmp_path) -> None:
    config_path = tmp_path / "services.json"

    config_path.write_text(
        "{ definitely not valid json",
        encoding="utf-8",
    )

    with pytest.raises(
        MonitoringConfigurationError,
        match="Invalid JSON",
    ):
        load_services(
            config_path,
            fake_http_session(),
        )


def test_service_without_checks_is_rejected(tmp_path) -> None:
    config_path = tmp_path / "services.json"

    config = {
        "services": [
            {
                "key": "test",
                "display_name": "Test Service",
                "checks": [],
            }
        ]
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        MonitoringConfigurationError,
        match="at least one check",
    ):
        load_services(
            config_path,
            fake_http_session(),
        )


def test_invalid_http_url_is_rejected(tmp_path) -> None:
    config_path = tmp_path / "services.json"

    config = {
        "services": [
            {
                "key": "test",
                "display_name": "Test Service",
                "checks": [
                    {
                        "type": "http",
                        "name": "HTTP availability",
                        "url": "banana://absolutely-not-http",
                    }
                ],
            }
        ]
    }

    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    with pytest.raises(
        MonitoringConfigurationError,
        match="Invalid HTTP URL",
    ):
        load_services(
            config_path,
            fake_http_session(),
        )