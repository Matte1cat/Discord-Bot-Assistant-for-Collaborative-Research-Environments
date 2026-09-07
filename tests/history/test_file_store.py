"""
Tests file-based monitoring history persistence, retrieval, filtering, and resilience.
"""
from datetime import datetime, timezone

import pytest

from history.file_store import FileHistoryStore
from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceResult,
    ServiceTransition,
)


def make_service_result(
    status: CheckStatus,
    service_key: str = "test-service",
    message: str = "test",
) -> ServiceResult:
    check_result = CheckResult(
        check_name="test-check",
        status=status,
        checked_at=datetime.now(timezone.utc),
        response_time_ms=123.4,
        message=message,
    )

    return ServiceResult(
        service_key=service_key,
        service_name="Test Service",
        status=status,
        check_results=(check_result,),
    )


def make_transition(
    previous_status: CheckStatus,
    current_status: CheckStatus,
) -> ServiceTransition:
    previous = make_service_result(previous_status)
    current = make_service_result(current_status)

    return ServiceTransition(
        service_key="test-service",
        service_name="Test Service",
        previous_status=previous_status,
        current_status=current_status,
        detected_at=datetime.now(timezone.utc),
        previous_result=previous,
        current_result=current,
    )


@pytest.mark.asyncio
async def test_service_result_can_be_written_and_read(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    result = make_service_result(
        CheckStatus.UP,
        message="HTTP 200",
    )

    await store.append_service_result(result)

    history = await store.get_recent_service_results(
        service_key="test-service",
        limit=5,
    )

    assert len(history) == 1

    entry = history[0]

    assert entry.service_key == "test-service"
    assert entry.service_name == "Test Service"
    assert entry.status is CheckStatus.UP

    assert len(entry.check_results) == 1

    check = entry.check_results[0]

    assert check.check_name == "test-check"
    assert check.status is CheckStatus.UP
    assert check.response_time_ms == 123.4
    assert check.message == "HTTP 200"


@pytest.mark.asyncio
async def test_recent_results_are_returned_newest_first(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    await store.append_service_result(
        make_service_result(CheckStatus.UP)
    )

    await store.append_service_result(
        make_service_result(CheckStatus.DOWN)
    )

    await store.append_service_result(
        make_service_result(CheckStatus.ERROR)
    )

    history = await store.get_recent_service_results(
        service_key="test-service",
        limit=2,
    )

    assert len(history) == 2

    assert history[0].status is CheckStatus.ERROR
    assert history[1].status is CheckStatus.DOWN


@pytest.mark.asyncio
async def test_results_are_filtered_by_service(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    await store.append_service_result(
        make_service_result(
            CheckStatus.UP,
            service_key="service-a",
        )
    )

    await store.append_service_result(
        make_service_result(
            CheckStatus.DOWN,
            service_key="service-b",
        )
    )

    history = await store.get_recent_service_results(
        service_key="service-a",
        limit=5,
    )

    assert len(history) == 1
    assert history[0].service_key == "service-a"
    assert history[0].status is CheckStatus.UP


@pytest.mark.asyncio
async def test_transition_can_be_written_and_read(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    transition = make_transition(
        CheckStatus.UP,
        CheckStatus.DOWN,
    )

    await store.append_transition(transition)

    history = await store.get_recent_transitions(
        service_key="test-service",
        limit=5,
    )

    assert len(history) == 1

    entry = history[0]

    assert entry.service_key == "test-service"
    assert entry.previous_status is CheckStatus.UP
    assert entry.current_status is CheckStatus.DOWN


@pytest.mark.asyncio
async def test_recent_transitions_are_returned_newest_first(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    await store.append_transition(
        make_transition(
            CheckStatus.UP,
            CheckStatus.DOWN,
        )
    )

    await store.append_transition(
        make_transition(
            CheckStatus.DOWN,
            CheckStatus.ERROR,
        )
    )

    await store.append_transition(
        make_transition(
            CheckStatus.ERROR,
            CheckStatus.UP,
        )
    )

    history = await store.get_recent_transitions(
        service_key="test-service",
        limit=2,
    )

    assert len(history) == 2

    assert (
        history[0].previous_status
        is CheckStatus.ERROR
    )
    assert (
        history[0].current_status
        is CheckStatus.UP
    )

    assert (
        history[1].previous_status
        is CheckStatus.DOWN
    )
    assert (
        history[1].current_status
        is CheckStatus.ERROR
    )


@pytest.mark.asyncio
async def test_missing_history_files_return_empty_results(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    results = await store.get_recent_service_results(
        service_key="test-service"
    )

    transitions = await store.get_recent_transitions(
        service_key="test-service"
    )

    assert results == ()
    assert transitions == ()


@pytest.mark.asyncio
async def test_invalid_history_line_is_ignored(
    tmp_path,
) -> None:
    history_directory = tmp_path / "history"

    store = FileHistoryStore(
        directory=history_directory
    )

    await store.append_service_result(
        make_service_result(CheckStatus.UP)
    )

    results_file = (
        history_directory
        / "service_results.jsonl"
    )

    with results_file.open(
        mode="a",
        encoding="utf-8",
    ) as file:
        file.write(
            "{ definitely not valid json }\n"
        )

    history = await store.get_recent_service_results(
        service_key="test-service",
        limit=5,
    )

    assert len(history) == 1
    assert history[0].status is CheckStatus.UP


@pytest.mark.asyncio
async def test_invalid_transition_line_is_ignored(
    tmp_path,
) -> None:
    history_directory = tmp_path / "history"

    store = FileHistoryStore(
        directory=history_directory
    )

    await store.append_transition(
        make_transition(
            CheckStatus.UP,
            CheckStatus.DOWN,
        )
    )

    transitions_file = (
        history_directory
        / "transitions.jsonl"
    )

    with transitions_file.open(
        mode="a",
        encoding="utf-8",
    ) as file:
        file.write("banana\n")

    history = await store.get_recent_transitions(
        service_key="test-service",
        limit=5,
    )

    assert len(history) == 1

    assert history[0].previous_status is CheckStatus.UP
    assert history[0].current_status is CheckStatus.DOWN


@pytest.mark.asyncio
async def test_history_limit_must_be_positive(
    tmp_path,
) -> None:
    store = FileHistoryStore(
        directory=tmp_path / "history"
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        await store.get_recent_service_results(
            service_key="test-service",
            limit=0,
        )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        await store.get_recent_transitions(
            service_key="test-service",
            limit=-1,
        )

@pytest.mark.asyncio
async def test_history_file_is_trimmed_when_size_limit_is_exceeded(
    tmp_path,
) -> None:
    history_directory = (
        tmp_path / "history"
    )

    store = FileHistoryStore(
        directory=history_directory,
        max_file_size_bytes=1500,
    )

    for index in range(20):
        await store.append_service_result(
            make_service_result(
                CheckStatus.UP,
                message=(
                    f"record-{index}-"
                    + ("x" * 100)
                ),
            )
        )

    results_file = (
        history_directory
        / "service_results.jsonl"
    )

    assert (
        results_file.stat().st_size
        <= 1500
    )

    content = results_file.read_text(
        encoding="utf-8"
    )

    assert "record-19-" in content

    assert "record-0-" not in content

@pytest.mark.asyncio
async def test_transition_file_is_trimmed_when_size_limit_is_exceeded(
    tmp_path,
) -> None:
    history_directory = (
        tmp_path / "history"
    )

    store = FileHistoryStore(
        directory=history_directory,
        max_file_size_bytes=1000,
    )

    for _ in range(30):
        await store.append_transition(
            make_transition(
                CheckStatus.UP,
                CheckStatus.DOWN,
            )
        )

    transitions_file = (
        history_directory
        / "transitions.jsonl"
    )

    assert (
        transitions_file.stat().st_size
        <= 1000
    )

    history = (
        await store.get_recent_transitions(
            service_key="test-service",
            limit=5,
        )
    )

    assert len(history) > 0

@pytest.mark.asyncio
async def test_service_history_is_trimmed_and_keeps_recent_records(
    tmp_path,
) -> None:
    history_directory = (
        tmp_path / "history"
    )

    max_size = 1500

    store = FileHistoryStore(
        directory=history_directory,
        max_file_size_bytes=max_size,
    )

    for index in range(30):
        await store.append_service_result(
            make_service_result(
                CheckStatus.UP,
                message=(
                    f"record-{index}-"
                    + ("x" * 100)
                ),
            )
        )

    results_file = (
        history_directory
        / "service_results.jsonl"
    )

    assert results_file.exists()
    assert results_file.stat().st_size <= max_size

    content = results_file.read_text(
        encoding="utf-8"
    )

    # The newest information must survive trimming.
    assert "record-29-" in content

    # Old records should have been discarded.
    assert "record-0-" not in content

    history = (
        await store.get_recent_service_results(
            service_key="test-service",
            limit=5,
        )
    )

    assert len(history) > 0
    assert (
        history[0].check_results[0].message
        == "record-29-" + ("x" * 100)
    )

@pytest.mark.asyncio
async def test_transition_history_is_trimmed_and_remains_readable(
    tmp_path,
) -> None:
    history_directory = (
        tmp_path / "history"
    )

    max_size = 1000

    store = FileHistoryStore(
        directory=history_directory,
        max_file_size_bytes=max_size,
    )

    for _ in range(30):
        await store.append_transition(
            make_transition(
                CheckStatus.UP,
                CheckStatus.DOWN,
            )
        )

    transitions_file = (
        history_directory
        / "transitions.jsonl"
    )

    assert transitions_file.exists()

    assert (
        transitions_file.stat().st_size
        <= max_size
    )

    history = (
        await store.get_recent_transitions(
            service_key="test-service",
            limit=5,
        )
    )

    assert len(history) > 0

    assert (
        history[0].previous_status
        is CheckStatus.UP
    )

    assert (
        history[0].current_status
        is CheckStatus.DOWN
    )

def test_history_max_file_size_must_be_positive(
    tmp_path,
) -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        FileHistoryStore(
            directory=tmp_path / "history",
            max_file_size_bytes=0,
        )