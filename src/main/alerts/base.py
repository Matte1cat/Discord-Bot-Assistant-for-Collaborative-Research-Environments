"""
Defines the notifier contract used to deliver monitoring transition events.
"""
from typing import Protocol

from monitoring.models import ServiceTransition


class TransitionNotifier(Protocol):
    async def notify(
        self,
        transition: ServiceTransition,
    ) -> None:
        ...