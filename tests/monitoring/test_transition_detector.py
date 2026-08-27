from datetime import datetime, timezone

import pytest

from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceResult,
)
from monitoring.transition_detector import detect_transition


def make_service_result(
    status: CheckStatus,
    service_key: str = "test-service",
) -> ServiceResult:
    check_result = CheckResult(
        check_name="test-check",
        status=status,
        checked_at=datetime.now(timezone.utc),
        response_time_ms=10.0,
        message="test",
    )

    return ServiceResult(
        service_key=service_key,
        service_name="Test Service",
        status=status,
        check_results=(check_result,),
    )


@pytest.mark.parametrize(
    ("previous_status", "current_status"),
    [
        (CheckStatus.UP, CheckStatus.DOWN),
        (CheckStatus.DOWN, CheckStatus.UP),
        (CheckStatus.UP, CheckStatus.ERROR),
        (CheckStatus.ERROR, CheckStatus.UP),
        (CheckStatus.DOWN, CheckStatus.ERROR),
        (CheckStatus.ERROR, CheckStatus.DOWN),
    ],
)
def test_status_change_creates_transition(
    previous_status: CheckStatus,
    current_status: CheckStatus,
) -> None:
    previous = make_service_result(previous_status)
    current = make_service_result(current_status)

    transition = detect_transition(
        previous,
        current,
    )

    assert transition is not None

    assert transition.service_key == "test-service"
    assert transition.previous_status is previous_status
    assert transition.current_status is current_status

    assert transition.previous_result is previous
    assert transition.current_result is current


@pytest.mark.parametrize(
    "status",
    [
        CheckStatus.UP,
        CheckStatus.DOWN,
        CheckStatus.ERROR,
    ],
)
def test_same_status_does_not_create_transition(
    status: CheckStatus,
) -> None:
    previous = make_service_result(status)
    current = make_service_result(status)

    transition = detect_transition(
        previous,
        current,
    )

    assert transition is None


@pytest.mark.parametrize(
    "initial_status",
    [
        CheckStatus.UP,
        CheckStatus.DOWN,
        CheckStatus.ERROR,
    ],
)
def test_initial_state_is_not_a_transition(
    initial_status: CheckStatus,
) -> None:
    current = make_service_result(initial_status)

    transition = detect_transition(
        None,
        current,
    )

    assert transition is None


def test_results_from_different_services_cannot_be_compared() -> None:
    previous = make_service_result(
        CheckStatus.UP,
        service_key="service-a",
    )

    current = make_service_result(
        CheckStatus.DOWN,
        service_key="service-b",
    )

    with pytest.raises(
        ValueError,
        match="different services",
    ):
        detect_transition(
            previous,
            current,
        )