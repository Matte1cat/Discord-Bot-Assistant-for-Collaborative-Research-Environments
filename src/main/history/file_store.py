"""
Provides file-based persistence and retrieval of monitoring results and transitions.
"""
import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from history.models import (
    ServiceHistoryEntry,
    TransitionHistoryEntry,
)
from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceResult,
    ServiceTransition,
)

DEFAULT_MAX_FILE_SIZE_BYTES = (
    25 * 1024 * 1024
)

TRIM_TARGET_RATIO = 0.80

logger = logging.getLogger(__name__)


class FileHistoryStore:
    def __init__(
        self,
        directory: Path,
        max_file_size_bytes: int = (
            DEFAULT_MAX_FILE_SIZE_BYTES
        ),
    ) -> None:
        if max_file_size_bytes <= 0:
            raise ValueError(
                (
                    "Maximum history file size "
                    "must be greater than zero."
                )
            )

        self._directory = directory

        self._max_file_size_bytes = (
            max_file_size_bytes
        )

        self._trim_target_bytes = int(
            max_file_size_bytes
            * TRIM_TARGET_RATIO
        )

        self._service_results_file = (
            directory / "service_results.jsonl"
        )

        self._transitions_file = (
            directory / "transitions.jsonl"
        )

        self._file_lock = asyncio.Lock()

    async def append_service_result(
        self,
        result: ServiceResult,
    ) -> None:
        record = {
            "recorded_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "service_key": result.service_key,
            "service_name": result.service_name,
            "status": result.status.value,
            "checks": [
                self._serialize_check_result(check)
                for check in result.check_results
            ],
        }

        await self._append_json_line(
            self._service_results_file,
            record,
        )

    async def append_transition(
        self,
        transition: ServiceTransition,
    ) -> None:
        record = {
            "detected_at": (
                transition.detected_at.isoformat()
            ),
            "service_key": transition.service_key,
            "service_name": transition.service_name,
            "previous_status": (
                transition.previous_status.value
            ),
            "current_status": (
                transition.current_status.value
            ),
        }

        await self._append_json_line(
            self._transitions_file,
            record,
        )

    async def get_recent_service_results(
        self,
        service_key: str,
        limit: int = 5,
    ) -> tuple[ServiceHistoryEntry, ...]:
        if limit <= 0:
            raise ValueError(
                "History limit must be greater than zero."
            )

        async with self._file_lock:
            return await asyncio.to_thread(
                self._read_service_results,
                service_key,
                limit,
            )

    async def get_recent_transitions(
        self,
        service_key: str,
        limit: int = 5,
    ) -> tuple[TransitionHistoryEntry, ...]:
        if limit <= 0:
            raise ValueError(
                "History limit must be greater than zero."
            )

        async with self._file_lock:
            return await asyncio.to_thread(
                self._read_transitions,
                service_key,
                limit,
            )

    @staticmethod
    def _serialize_check_result(
        result: CheckResult,
    ) -> dict[str, Any]:
        return {
            "check_name": result.check_name,
            "status": result.status.value,
            "checked_at": (
                result.checked_at.isoformat()
            ),
            "response_time_ms": (
                result.response_time_ms
            ),
            "message": result.message,
        }

    async def _append_json_line(
        self,
        path: Path,
        record: dict[str, Any],
    ) -> None:
        serialized = json.dumps(
            record,
            ensure_ascii=False,
        )

        async with self._file_lock:
            await asyncio.to_thread(
                self._write_line,
                path,
                serialized,
            )

    def _write_line(
        self,
        path: Path,
        serialized: str,
    ) -> None:
        self._directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            mode="a",
            encoding="utf-8",
        ) as file:
            file.write(serialized)
            file.write("\n")

        self._trim_file_if_needed(
            path
        )

    def _trim_file_if_needed(
        self,
        path: Path,
    ) -> None:
        try:
            current_size = path.stat().st_size

        except FileNotFoundError:
            return

        if (
            current_size
            <= self._max_file_size_bytes
        ):
            return

        with path.open(
            mode="rb",
        ) as file:
            lines = file.readlines()

        retained_lines: list[bytes] = []
        retained_size = 0

        for line in reversed(
            lines
        ):
            line_size = len(
                line
            )

            if (
                retained_lines
                and retained_size + line_size
                > self._trim_target_bytes
            ):
                break

            retained_lines.append(
                line
            )

            retained_size += (
                line_size
            )

        retained_lines.reverse()

        temporary_path = path.with_name(
            f".{path.name}.trim.tmp"
        )

        try:
            with temporary_path.open(
                mode="wb",
            ) as file:
                file.writelines(
                    retained_lines
                )

            temporary_path.replace(
                path
            )

        finally:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

        logger.info(
            (
                "History file trimmed "
                "| file=%s "
                "| previous_bytes=%d "
                "| retained_bytes=%d"
            ),
            path.name,
            current_size,
            retained_size,
        )

    def _read_service_results(
        self,
        service_key: str,
        limit: int,
    ) -> tuple[ServiceHistoryEntry, ...]:
        if not self._service_results_file.exists():
            return ()

        entries: deque[ServiceHistoryEntry] = deque(
            maxlen=limit
        )

        with self._service_results_file.open(
            mode="r",
            encoding="utf-8",
        ) as file:
            for line_number, line in enumerate(
                file,
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)

                    if (
                        record.get("service_key")
                        != service_key
                    ):
                        continue

                    entries.append(
                        self._deserialize_service_result(
                            record
                        )
                    )

                except (
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    logger.warning(
                        (
                            "Invalid service history record "
                            "ignored | line=%d | error=%s"
                        ),
                        line_number,
                        exc,
                        extra={
                            "service": service_key,
                            "check": "-",
                        },
                    )

        return tuple(reversed(entries))

    def _read_transitions(
        self,
        service_key: str,
        limit: int,
    ) -> tuple[TransitionHistoryEntry, ...]:
        if not self._transitions_file.exists():
            return ()

        entries: deque[TransitionHistoryEntry] = deque(
            maxlen=limit
        )

        with self._transitions_file.open(
            mode="r",
            encoding="utf-8",
        ) as file:
            for line_number, line in enumerate(
                file,
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)

                    if (
                        record.get("service_key")
                        != service_key
                    ):
                        continue

                    entries.append(
                        self._deserialize_transition(
                            record
                        )
                    )

                except (
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    logger.warning(
                        (
                            "Invalid transition history "
                            "record ignored | "
                            "line=%d | error=%s"
                        ),
                        line_number,
                        exc,
                        extra={
                            "service": service_key,
                            "check": "-",
                        },
                    )

        return tuple(reversed(entries))

    @staticmethod
    def _deserialize_service_result(
        record: dict[str, Any],
    ) -> ServiceHistoryEntry:
        checks = tuple(
            CheckResult(
                check_name=check["check_name"],
                status=CheckStatus(
                    check["status"]
                ),
                checked_at=datetime.fromisoformat(
                    check["checked_at"]
                ),
                response_time_ms=check.get(
                    "response_time_ms"
                ),
                message=check.get("message"),
            )
            for check in record["checks"]
        )

        return ServiceHistoryEntry(
            recorded_at=datetime.fromisoformat(
                record["recorded_at"]
            ),
            service_key=record["service_key"],
            service_name=record["service_name"],
            status=CheckStatus(record["status"]),
            check_results=checks,
        )

    @staticmethod
    def _deserialize_transition(
        record: dict[str, Any],
    ) -> TransitionHistoryEntry:
        return TransitionHistoryEntry(
            detected_at=datetime.fromisoformat(
                record["detected_at"]
            ),
            service_key=record["service_key"],
            service_name=record["service_name"],
            previous_status=CheckStatus(
                record["previous_status"]
            ),
            current_status=CheckStatus(
                record["current_status"]
            ),
        )