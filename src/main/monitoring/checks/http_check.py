"""
Implements HTTP-based availability checks for monitored web services.
"""
from datetime import datetime, timezone
from time import perf_counter

import aiohttp

from monitoring.checks.base import BaseCheck
from monitoring.models import CheckResult, CheckStatus


class HTTPCheck(BaseCheck):
    def __init__(
        self,
        name: str,
        url: str,
        session: aiohttp.ClientSession,
        expected_status: int = 200,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(name)

        self.url = url
        self.session = session
        self.expected_status = expected_status
        self.timeout_seconds = timeout_seconds

    async def run(self) -> CheckResult:
        started_at = perf_counter()

        try:
            timeout = aiohttp.ClientTimeout(
                total=self.timeout_seconds
            )

            async with self.session.get(
                self.url,
                timeout=timeout,
            ) as response:
                response_time_ms = (
                    perf_counter() - started_at
                ) * 1000

                if response.status == self.expected_status:
                    status = CheckStatus.UP
                else:
                    status = CheckStatus.DOWN

                return CheckResult(
                    check_name=self.name,
                    status=status,
                    checked_at=datetime.now(timezone.utc),
                    response_time_ms=response_time_ms,
                    message=f"HTTP {response.status}",
                )

        except TimeoutError:
            response_time_ms = (
                perf_counter() - started_at
            ) * 1000

            return CheckResult(
                check_name=self.name,
                status=CheckStatus.DOWN,
                checked_at=datetime.now(timezone.utc),
                response_time_ms=response_time_ms,
                message="Request timed out",
            )

        except aiohttp.ClientError as exc:
            response_time_ms = (
                perf_counter() - started_at
            ) * 1000

            return CheckResult(
                check_name=self.name,
                status=CheckStatus.DOWN,
                checked_at=datetime.now(timezone.utc),
                response_time_ms=response_time_ms,
                message=str(exc),
            )