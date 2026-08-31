"""
Tests service registration, check execution, aggregation, and failure handling.
"""
from datetime import datetime, timezone

import pytest

from monitoring.checks.base import BaseCheck
from monitoring.manager import MonitoringManager
from monitoring.models import CheckResult, CheckStatus
from monitoring.service import Service


class StubCheck(BaseCheck):
    """Simple deterministic check used to test the manager."""

    def __init__(
        self,
        name: str,
        status: CheckStatus,
    ) -> None:
        super().__init__(name)
        self.status = status

    async def run(self) -> CheckResult:
        return CheckResult(
            check_name=self.name,
            status=self.status,
            checked_at=datetime.now(timezone.utc),
            response_time_ms=10.0,
            message="stub",
        )


class ExplodingCheck(BaseCheck):
    """Check used to simulate an unexpected internal exception."""

    async def run(self) -> CheckResult:
        raise RuntimeError("Boom")


@pytest.mark.asyncio
async def test_service_is_up_when_all_checks_are_up() -> None:
    manager = MonitoringManager()

    service = Service(
        key="test",
        display_name="Test Service",
        checks=(
            StubCheck("check-a", CheckStatus.UP),
            StubCheck("check-b", CheckStatus.UP),
        ),
    )

    manager.register(service)

    result = await manager.check_service("test")

    assert result.status is CheckStatus.UP
    assert len(result.check_results) == 2


@pytest.mark.asyncio
async def test_service_is_down_when_a_check_is_down() -> None:
    manager = MonitoringManager()

    service = Service(
        key="test",
        display_name="Test Service",
        checks=(
            StubCheck("check-a", CheckStatus.UP),
            StubCheck("check-b", CheckStatus.DOWN),
        ),
    )

    manager.register(service)

    result = await manager.check_service("test")

    assert result.status is CheckStatus.DOWN


@pytest.mark.asyncio
async def test_service_is_error_when_a_check_returns_error() -> None:
    manager = MonitoringManager()

    service = Service(
        key="test",
        display_name="Test Service",
        checks=(
            StubCheck("check-a", CheckStatus.UP),
            StubCheck("check-b", CheckStatus.ERROR),
        ),
    )

    manager.register(service)

    result = await manager.check_service("test")

    assert result.status is CheckStatus.ERROR


@pytest.mark.asyncio
async def test_unexpected_check_exception_becomes_error() -> None:
    manager = MonitoringManager()

    service = Service(
        key="test",
        display_name="Test Service",
        checks=(
            ExplodingCheck("exploding-check"),
        ),
    )

    manager.register(service)

    result = await manager.check_service("test")

    assert result.status is CheckStatus.ERROR
    assert len(result.check_results) == 1

    check_result = result.check_results[0]

    assert check_result.status is CheckStatus.ERROR
    assert check_result.message is not None
    assert "RuntimeError" in check_result.message


def test_duplicate_service_registration_is_rejected() -> None:
    manager = MonitoringManager()

    service = Service(
        key="test",
        display_name="Test Service",
        checks=(
            StubCheck("check", CheckStatus.UP),
        ),
    )

    manager.register(service)

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        manager.register(service)