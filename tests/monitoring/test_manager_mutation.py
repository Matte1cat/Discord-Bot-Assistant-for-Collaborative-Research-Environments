"""
Tests live replacement and removal of monitored services and runtime state.
"""

from datetime import datetime, timezone

import pytest

from monitoring.checks.base import BaseCheck
from monitoring.manager import MonitoringManager
from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceResult,
)
from monitoring.service import Service
from monitoring.state_store import (
    MonitoringStateStore,
)


class StubCheck(BaseCheck):
    async def run(
        self,
    ) -> CheckResult:
        return CheckResult(
            check_name=self.name,
            status=CheckStatus.UP,
            checked_at=datetime.now(
                timezone.utc
            ),
            response_time_ms=1.0,
            message="ok",
        )


def make_service(
    key: str,
    *check_names: str,
) -> Service:
    return Service(
        key=key,
        display_name=f"Service {key}",
        checks=tuple(
            StubCheck(name)
            for name in check_names
        ),
    )


def test_replace_registered_service() -> None:
    manager = MonitoringManager()

    original = make_service(
        "service-a",
        "first",
    )

    replacement = make_service(
        "service-a",
        "first",
        "second",
    )

    manager.register(
        original
    )

    manager.replace(
        replacement
    )

    current = manager.get_service(
        "service-a"
    )

    assert current is replacement
    assert len(current.checks) == 2


def test_replace_unknown_service_is_rejected() -> None:
    manager = MonitoringManager()

    with pytest.raises(
        KeyError,
        match="not registered",
    ):
        manager.replace(
            make_service(
                "missing",
                "check",
            )
        )


def test_unregister_service() -> None:
    manager = MonitoringManager()

    service = make_service(
        "service-a",
        "check",
    )

    manager.register(
        service
    )

    removed = manager.unregister(
        "service-a"
    )

    assert removed is service

    assert (
        manager.get_service(
            "service-a"
        )
        is None
    )


def test_unregister_unknown_service_is_rejected() -> None:
    manager = MonitoringManager()

    with pytest.raises(
        KeyError,
        match="not registered",
    ):
        manager.unregister(
            "missing"
        )


def test_state_store_remove_clears_previous_state() -> None:
    store = MonitoringStateStore()

    result = ServiceResult(
        service_key="service-a",
        service_name="Service A",
        status=CheckStatus.DOWN,
        check_results=(),
    )

    store.update(
        result
    )

    removed = store.remove(
        "service-a"
    )

    assert removed is result

    assert (
        store.get(
            "service-a"
        )
        is None
    )


def test_removing_missing_state_is_safe() -> None:
    store = MonitoringStateStore()

    assert (
        store.remove(
            "missing"
        )
        is None
    )