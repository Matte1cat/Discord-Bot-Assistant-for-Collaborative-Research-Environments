"""
Coordinates service check execution and produces aggregate monitoring results.
"""
import asyncio
import logging

from datetime import datetime, timezone
from time import perf_counter

from monitoring.checks.base import BaseCheck
from monitoring.models import (
    CheckResult,
    CheckStatus,
    ServiceResult,
)
from monitoring.service import Service

logger = logging.getLogger(__name__)

class MonitoringManager:
    def __init__(self) -> None:
        self._services: dict[str, Service] = {}

    async def _run_check(
        self,
        service: Service,
        check: BaseCheck,
    ) -> CheckResult:
        check_logger = logging.LoggerAdapter(
            logger,
            {
                "service": service.key,
                "check": check.name,
            },
        )

        check_logger.debug("Starting check")

        started_at = perf_counter()

        try:
            result = await check.run()

        except Exception as exc:
            response_time_ms = (
                perf_counter() - started_at
            ) * 1000

            check_logger.exception(
                "Unexpected check failure | duration_ms=%.1f",
                response_time_ms,
            )

            return CheckResult(
                check_name=check.name,
                status=CheckStatus.ERROR,
                checked_at=datetime.now(timezone.utc),
                response_time_ms=response_time_ms,
                message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if result.status is CheckStatus.UP:
            log_level = logging.DEBUG
        elif result.status is CheckStatus.DOWN:
            log_level = logging.WARNING
        else:
            log_level = logging.ERROR

        check_logger.log(
            log_level,
            (
                "Check completed | status=%s | "
                "response_time_ms=%s | details=%s"
            ),
            result.status.value.upper(),
            (
                f"{result.response_time_ms:.1f}"
                if result.response_time_ms is not None
                else "N/A"
            ),
            result.message or "N/A",
        )

        return result

    def register(self, service: Service) -> None:
        if service.key in self._services:
            raise ValueError(
                f"Service '{service.key}' is already registered."
            )

        self._services[service.key] = service

    def get_service(self, key: str) -> Service | None:
        return self._services.get(key)

    def list_services(self) -> tuple[Service, ...]:
        return tuple(self._services.values())

    async def check_service(self, key: str) -> ServiceResult:
        service = self.get_service(key)

        if service is None:
            raise KeyError(f"Unknown service: '{key}'")

        results = tuple(
            await asyncio.gather(
                *(
                    self._run_check(service, check)
                    for check in service.checks
                )
            )
        )

        if any(
            result.status is CheckStatus.ERROR
            for result in results
        ):
            overall_status = CheckStatus.ERROR

        elif any(
            result.status is CheckStatus.DOWN
            for result in results
        ):
            overall_status = CheckStatus.DOWN

        else:
            overall_status = CheckStatus.UP

        return ServiceResult(
            service_key=service.key,
            service_name=service.display_name,
            status=overall_status,
            check_results=results,
        )