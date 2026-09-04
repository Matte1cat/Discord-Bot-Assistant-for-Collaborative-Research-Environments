"""
Tests persistent creation and removal of configured services and checks.
"""

import json

import pytest

from monitoring.service_config_store import (
    ServiceConfigStore,
    ServiceConfigStoreError,
)


def write_config(
    path,
) -> None:
    path.write_text(
        json.dumps(
            {
                "services": [
                    {
                        "key": "service-a",
                        "display_name": "Service A",
                        "checks": [
                            {
                                "type": "http",
                                "name": "Primary",
                                "url": "https://example.com/",
                                "expected_status": 200,
                                "timeout_seconds": 5.0,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_add_service(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    await store.add_service(
        {
            "key": "service-b",
            "display_name": "Service B",
            "checks": [
                {
                    "type": "http",
                    "name": "Availability",
                    "url": "https://example.org/",
                    "expected_status": 200,
                    "timeout_seconds": 5.0,
                }
            ],
        }
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert len(root["services"]) == 2

    assert (
        root["services"][1]["key"]
        == "service-b"
    )


@pytest.mark.asyncio
async def test_duplicate_service_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    with pytest.raises(
        ServiceConfigStoreError,
        match="already exists",
    ):
        await store.add_service(
            {
                "key": "service-a",
                "display_name": "Duplicate",
                "checks": [],
            }
        )


@pytest.mark.asyncio
async def test_add_check(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    await store.add_check(
        service_key="service-a",
        check_config={
            "type": "http",
            "name": "Secondary",
            "url": "https://example.org/",
            "expected_status": 204,
            "timeout_seconds": 3.0,
        },
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    checks = root["services"][0]["checks"]

    assert len(checks) == 2
    assert checks[1]["name"] == "Secondary"


@pytest.mark.asyncio
async def test_duplicate_check_name_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    with pytest.raises(
        ServiceConfigStoreError,
        match="already exists",
    ):
        await store.add_check(
            service_key="service-a",
            check_config={
                "type": "http",
                "name": "primary",
                "url": "https://example.org/",
            },
        )


@pytest.mark.asyncio
async def test_remove_check(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    await store.add_check(
        service_key="service-a",
        check_config={
            "type": "http",
            "name": "Secondary",
            "url": "https://example.org/",
            "expected_status": 200,
            "timeout_seconds": 5.0,
        },
    )

    await store.remove_check(
        service_key="service-a",
        check_name="Secondary",
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    checks = root["services"][0]["checks"]

    assert len(checks) == 1
    assert checks[0]["name"] == "Primary"


@pytest.mark.asyncio
async def test_last_check_cannot_be_removed(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    with pytest.raises(
        ServiceConfigStoreError,
        match="last check",
    ):
        await store.remove_check(
            service_key="service-a",
            check_name="Primary",
        )


@pytest.mark.asyncio
async def test_remove_service(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    await store.remove_service(
        "service-a"
    )

    root = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert root["services"] == []


@pytest.mark.asyncio
async def test_unknown_service_cannot_be_removed(
    tmp_path,
) -> None:
    path = tmp_path / "services.json"
    write_config(path)

    store = ServiceConfigStore(path)

    with pytest.raises(
        ServiceConfigStoreError,
        match="does not exist",
    ):
        await store.remove_service(
            "missing"
        )