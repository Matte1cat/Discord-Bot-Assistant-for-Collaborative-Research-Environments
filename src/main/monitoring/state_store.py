"""
Maintains the latest in-memory monitoring result for each configured service.
"""
from monitoring.models import ServiceResult


class MonitoringStateStore:
    def __init__(self) -> None:
        self._states: dict[str, ServiceResult] = {}

    def get(
        self,
        service_key: str,
    ) -> ServiceResult | None:
        return self._states.get(service_key)

    def update(
        self,
        result: ServiceResult,
    ) -> ServiceResult | None:
        previous_result = self._states.get(
            result.service_key
        )

        self._states[result.service_key] = result

        return previous_result

    def list_states(
        self,
    ) -> tuple[ServiceResult, ...]:
        return tuple(self._states.values())

    def remove(
        self,
        service_key: str,
    ) -> ServiceResult | None:
        return self._states.pop(
            service_key,
            None,
        )