"""
Defines persistent history records reconstructed from stored monitoring data.
"""
from dataclasses import dataclass
from datetime import datetime

from monitoring.models import CheckResult, CheckStatus


@dataclass(frozen=True)
class ServiceHistoryEntry:
    recorded_at: datetime
    service_key: str
    service_name: str
    status: CheckStatus
    check_results: tuple[CheckResult, ...]


@dataclass(frozen=True)
class TransitionHistoryEntry:
    detected_at: datetime
    service_key: str
    service_name: str
    previous_status: CheckStatus
    current_status: CheckStatus