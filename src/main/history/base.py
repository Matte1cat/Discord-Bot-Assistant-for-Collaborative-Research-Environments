"""
Defines the storage contract for monitoring results and transition history.
"""
from typing import Protocol

from history.models import (
    ServiceHistoryEntry,
    TransitionHistoryEntry,
)
from monitoring.models import (
    ServiceResult,
    ServiceTransition,
)


class HistoryStore(Protocol):
    async def append_service_result(
        self,
        result: ServiceResult,
    ) -> None:
        ...

    async def append_transition(
        self,
        transition: ServiceTransition,
    ) -> None:
        ...

    async def get_recent_service_results(
        self,
        service_key: str,
        limit: int = 5,
    ) -> tuple[ServiceHistoryEntry, ...]:
        ...

    async def get_recent_transitions(
        self,
        service_key: str,
        limit: int = 5,
    ) -> tuple[TransitionHistoryEntry, ...]:
        ...