"""
Tests scheduler lifecycle, transition processing, and notifier failure isolation.
"""
from datetime import datetime, timezone

import asyncio
import pytest

from monitoring.checks.base import BaseCheck
from monitoring.manager import MonitoringManager
from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceTransition,
)
from monitoring.scheduler import MonitoringScheduler
from monitoring.service import Service
from monitoring.state_store import MonitoringStateStore


class SequenceCheck(BaseCheck):
    """
    Check that returns a predefined sequence of states.

    Useful for simulating:
    UP -> UP -> DOWN -> DOWN -> UP
    """

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


class RecordingNotifier:
    def __init__(self) -> None:
        self.transitions: list[ServiceTransition] = []

    async def notify(
        self,
        transition: ServiceTransition,
    ) -> None:
        self.transitions.append(transition)


class ExplodingNotifier:
    async def notify(
        self,
        transition: ServiceTransition,
    ) -> None:
        raise RuntimeError(
            "Simulated notification failure"
        )


def build_scheduler(
    statuses: list[CheckStatus],
    *notifiers,
) -> MonitoringScheduler:
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

    state_store = MonitoringStateStore()

    return MonitoringScheduler(
        manager=manager,
        state_store=state_store,
        interval_seconds=60,
        notifiers=tuple(notifiers),
    )


@pytest.mark.asyncio
async def test_scheduler_detects_only_real_transitions() -> None:
    notifier = RecordingNotifier()

    scheduler = build_scheduler(
        [
            CheckStatus.UP,
            CheckStatus.UP,
            CheckStatus.DOWN,
            CheckStatus.DOWN,
            CheckStatus.UP,
        ],
        notifier,
    )

    # First cycle:
    # NONE -> UP
    # Baseline, not a transition.
    cycle = await scheduler.run_cycle()

    assert len(cycle.transitions) == 0
    assert len(notifier.transitions) == 0

    # Second cycle:
    # UP -> UP
    cycle = await scheduler.run_cycle()

    assert len(cycle.transitions) == 0
    assert len(notifier.transitions) == 0

    # Third cycle:
    # UP -> DOWN
    cycle = await scheduler.run_cycle()

    assert len(cycle.transitions) == 1
    assert len(notifier.transitions) == 1

    first_transition = notifier.transitions[0]

    assert (
        first_transition.previous_status
        is CheckStatus.UP
    )
    assert (
        first_transition.current_status
        is CheckStatus.DOWN
    )

    # Fourth cycle:
    # DOWN -> DOWN
    # Must NOT generate another alert.
    cycle = await scheduler.run_cycle()

    assert len(cycle.transitions) == 0
    assert len(notifier.transitions) == 1

    # Fifth cycle:
    # DOWN -> UP
    cycle = await scheduler.run_cycle()

    assert len(cycle.transitions) == 1
    assert len(notifier.transitions) == 2

    second_transition = notifier.transitions[1]

    assert (
        second_transition.previous_status
        is CheckStatus.DOWN
    )
    assert (
        second_transition.current_status
        is CheckStatus.UP
    )


@pytest.mark.asyncio
async def test_notifier_failure_does_not_break_monitoring() -> None:
    recording_notifier = RecordingNotifier()
    exploding_notifier = ExplodingNotifier()

    scheduler = build_scheduler(
        [
            CheckStatus.UP,
            CheckStatus.DOWN,
        ],
        exploding_notifier,
        recording_notifier,
    )

    # Establish baseline.
    first_cycle = await scheduler.run_cycle()

    assert len(first_cycle.transitions) == 0

    # Generate UP -> DOWN transition.
    #
    # ExplodingNotifier will raise an exception,
    # but the scheduler must catch it and continue.
    second_cycle = await scheduler.run_cycle()

    assert len(second_cycle.transitions) == 1

    # The second notifier must still have been executed.
    assert len(recording_notifier.transitions) == 1

    transition = recording_notifier.transitions[0]

    assert transition.previous_status is CheckStatus.UP
    assert transition.current_status is CheckStatus.DOWN


@pytest.mark.asyncio
async def test_scheduler_can_start_and_stop_cleanly() -> None:
    manager = MonitoringManager()
    state_store = MonitoringStateStore()

    scheduler = MonitoringScheduler(
        manager=manager,
        state_store=state_store,
        interval_seconds=60,
    )

    assert scheduler.is_running is False

    scheduler.start()

    assert scheduler.is_running is True

    # Gives the newly created asyncio task
    # an opportunity to start running.
    await asyncio.sleep(0)

    await scheduler.stop()

    assert scheduler.is_running is False