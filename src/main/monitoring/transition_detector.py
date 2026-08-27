from datetime import datetime, timezone

from monitoring.models import (
    ServiceResult,
    ServiceTransition,
)


def detect_transition(
    previous: ServiceResult | None,
    current: ServiceResult,
) -> ServiceTransition | None:
    if previous is None:
        return None

    if previous.service_key != current.service_key:
        raise ValueError(
            "Cannot compare monitoring results "
            "from different services."
        )

    if previous.status is current.status:
        return None

    return ServiceTransition(
        service_key=current.service_key,
        service_name=current.service_name,
        previous_status=previous.status,
        current_status=current.status,
        detected_at=datetime.now(timezone.utc),
        previous_result=previous,
        current_result=current,
    )