from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CheckStatus(Enum):
    UP = "up"
    DOWN = "down"
    ERROR = "error"


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    status: CheckStatus
    checked_at: datetime
    response_time_ms: float | None = None
    message: str | None = None

@dataclass(frozen=True)
class ServiceResult:
    service_key: str
    service_name: str
    status: CheckStatus
    check_results: tuple[CheckResult, ...]

@dataclass(frozen=True)
class ServiceTransition:
    service_key: str
    service_name: str
    previous_status: CheckStatus
    current_status: CheckStatus
    detected_at: datetime
    previous_result: ServiceResult
    current_result: ServiceResult

@dataclass(frozen=True)
class MonitoringCycleResult:
    service_results: tuple[ServiceResult, ...]
    transitions: tuple[ServiceTransition, ...]