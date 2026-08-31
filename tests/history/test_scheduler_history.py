"""
Tests integration between periodic monitoring and persistent history storage.
"""
from datetime import datetime, timezone

import pytest

from monitoring.checks.base import BaseCheck
from monitoring.manager import MonitoringManager
from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceResult,
    ServiceTransition,
)
from monitoring.scheduler import MonitoringScheduler
from monitoring.service import Service
from monitoring.state_store import MonitoringStateStore


class SequenceCheck(BaseCheck):
    def __init__(
        self,
        name: str,
        statuses: list[CheckStatus],
    ) -> None:
        super().__init__(name)

        if not statuses:
            raise ValueError(
                "SequenceCheck requires at least one status."
            )

        self._statuses = statuses
        self._index = 0

    async def run(self) -> CheckResult:
        if self._index < len(self._statuses):
            status = self._statuses[self._index]
            self._index += 1
        else:
            status = self._statuses[-1]

        return CheckResult(
            check_name=self.name,
            status=status,
            checked_at=datetime.now(timezone.utc),
            response_time_ms=10.0,
            message="sequence check",
        )


class RecordingHistoryStore:
    def __init__(self) -> None:
        self.service_results: list[
            ServiceResult
        ] = []

        self.transitions: list[
            ServiceTransition
        ] = []

    async def append_service_result(
        self,
        result: ServiceResult,
    ) -> None:
        self.service_results.append(result)

    async def append_transition(
        self,
        transition: ServiceTransition,
    ) -> None:
        self.transitions.append(transition)

    async def get_recent_service_results(
        self,
        service_key: str,
        limit: int = 5,
    ):
        return ()

    async def get_recent_transitions(
        self,
        service_key: str,
        limit: int = 5,
    ):
        return ()


class ExplodingHistoryStore:
    async def append_service_result(
        self,
        result: ServiceResult,
    ) -> None:
        raise OSError(
            "Simulated filesystem failure"
        )

    async def append_transition(
        self,
        transition: ServiceTransition,
    ) -> None:
        raise OSError(
            "Simulated filesystem failure"
        )

    async def get_recent_service_results(
        self,
        service_key: str,
        limit: int = 5,
    ):
        return ()

    async def get_recent_transitions(
        self,
        service_key: str,
        limit: int = 5,
    ):
        return ()


class RecordingNotifier:
    def __init__(self) -> None:
        self.transitions: list[
            ServiceTransition
        ] = []

    async def notify(
        self,
        transition: ServiceTransition,
    ) -> None:
        self.transitions.append(transition)


def build_manager(
    statuses: list[CheckStatus],
) -> MonitoringManager:
    manager = MonitoringManager()

    service = Service(
        key="test-service",
        display_name="Test Service",
        checks=(
            SequenceCheck(
                name="sequence-check",
                statuses=statuses,
            ),
        ),
    )

    manager.register(service)

    return manager


@pytest.mark.asyncio
async def test_scheduler_persists_every_service_result() -> None:
    manager = build_manager(
        [
            CheckStatus.UP,
            CheckStatus.DOWN,
            CheckStatus.DOWN,
        ]
    )

    history_store = RecordingHistoryStore()

    scheduler = MonitoringScheduler(
        manager=manager,
        state_store=MonitoringStateStore(),
        interval_seconds=60,
        history_store=history_store,
    )

    await scheduler.run_cycle()
    await scheduler.run_cycle()
    await scheduler.run_cycle()

    assert len(history_store.service_results) == 3

    assert (
        history_store.service_results[0].status
        is CheckStatus.UP
    )

    assert (
        history_store.service_results[1].status
        is CheckStatus.DOWN
    )

    assert (
        history_store.service_results[2].status
        is CheckStatus.DOWN
    )


@pytest.mark.asyncio
async def test_scheduler_persists_only_real_transitions() -> None:
    manager = build_manager(
        [
            CheckStatus.UP,
            CheckStatus.UP,
            CheckStatus.DOWN,
            CheckStatus.DOWN,
            CheckStatus.UP,
        ]
    )

    history_store = RecordingHistoryStore()

    scheduler = MonitoringScheduler(
        manager=manager,
        state_store=MonitoringStateStore(),
        interval_seconds=60,
        history_store=history_store,
    )

    for _ in range(5):
        await scheduler.run_cycle()

    assert len(history_store.service_results) == 5

    assert len(history_store.transitions) == 2

    first_transition = history_store.transitions[0]

    assert (
        first_transition.previous_status
        is CheckStatus.UP
    )
    assert (
        first_transition.current_status
        is CheckStatus.DOWN
    )

    second_transition = history_store.transitions[1]

    assert (
        second_transition.previous_status
        is CheckStatus.DOWN
    )
    assert (
        second_transition.current_status
        is CheckStatus.UP
    )


@pytest.mark.asyncio
async def test_history_failure_does_not_break_monitoring() -> None:
    manager = build_manager(
        [
            CheckStatus.UP,
            CheckStatus.DOWN,
        ]
    )

    notifier = RecordingNotifier()

    scheduler = MonitoringScheduler(
        manager=manager,
        state_store=MonitoringStateStore(),
        interval_seconds=60,
        history_store=ExplodingHistoryStore(),
        notifiers=(notifier,),
    )

    first_cycle = await scheduler.run_cycle()

    assert len(first_cycle.service_results) == 1
    assert len(first_cycle.transitions) == 0

    second_cycle = await scheduler.run_cycle()

    assert len(second_cycle.service_results) == 1
    assert len(second_cycle.transitions) == 1

    transition = second_cycle.transitions[0]

    assert transition.previous_status is CheckStatus.UP
    assert transition.current_status is CheckStatus.DOWN

    # Persistence failed, but notification still happened.
    assert len(notifier.transitions) == 1

    assert (
        notifier.transitions[0].current_status
        is CheckStatus.DOWN
    )