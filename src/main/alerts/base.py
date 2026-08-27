from typing import Protocol

from monitoring.models import ServiceTransition


class TransitionNotifier(Protocol):
    async def notify(
        self,
        transition: ServiceTransition,
    ) -> None:
        ...