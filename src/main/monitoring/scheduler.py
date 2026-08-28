import asyncio
import logging

from monitoring.manager import MonitoringManager
from monitoring.models import (
    MonitoringCycleResult,
    ServiceResult,
    ServiceTransition,
)
from monitoring.transition_detector import detect_transition
from monitoring.state_store import MonitoringStateStore

from alerts.base import TransitionNotifier

from history.base import HistoryStore


logger = logging.getLogger(__name__)


class MonitoringScheduler:
    def __init__(
        self,
        manager: MonitoringManager,
        state_store: MonitoringStateStore,
        interval_seconds: float,
        history_store: HistoryStore | None = None,
        notifiers: tuple[TransitionNotifier, ...] = (),
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(
                "Monitoring interval must be greater than zero."
            )

        self._manager = manager
        self._state_store = state_store
        self._interval_seconds = interval_seconds
        self._history_store = history_store
        self._notifiers = notifiers

        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    def start(self) -> None:
        if self.is_running:
            logger.warning(
                "Monitoring scheduler is already running."
            )
            return

        self._task = asyncio.create_task(
            self._run_loop(),
            name="monitoring-scheduler",
        )

        logger.info(
            "Monitoring scheduler started | interval_seconds=%.1f",
            self._interval_seconds,
        )

    async def stop(self) -> None:
        if self._task is None:
            return

        if not self._task.done():
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._task = None

        logger.info("Monitoring scheduler stopped.")

    async def run_cycle(self) -> MonitoringCycleResult:
        services = self._manager.list_services()

        if not services:
            logger.debug(
                "Monitoring cycle skipped: no services registered."
            )

            return MonitoringCycleResult(
                service_results=(),
                transitions=(),
            )

        logger.debug(
            "Starting monitoring cycle | services=%d",
            len(services),
        )

        results = await asyncio.gather(
            *(
                self._check_service(service.key)
                for service in services
            )
        )

        completed_results = tuple(
            result
            for result in results
            if result is not None
        )

        for result in completed_results:
            await self._persist_service_result(
                result
            )

        transitions = []

        for result in completed_results:
            previous_result = self._state_store.update(
                result
            )

            transition = detect_transition(
                previous_result,
                result,
            )

            if previous_result is None:
                logger.debug(
                    "Initial monitoring state stored | current=%s",
                    result.status.value.upper(),
                    extra={
                        "service": result.service_key,
                        "check": "-",
                    },
                )

            elif transition is None:
                logger.debug(
                    "Monitoring state unchanged | current=%s",
                    result.status.value.upper(),
                    extra={
                        "service": result.service_key,
                        "check": "-",
                    },
                )

            else:
                transitions.append(transition)

                logger.info(
                    (
                        "Service state transition detected | "
                        "previous=%s | current=%s"
                    ),
                    transition.previous_status.value.upper(),
                    transition.current_status.value.upper(),
                    extra={
                        "service": transition.service_key,
                        "check": "-",
                    },
                )

        for transition in transitions:
            await self._persist_transition(
                transition
            )

            await self._notify_transition(
                transition
            )

        logger.debug(
            (
                "Monitoring cycle completed | "
                "services=%d | transitions=%d"
            ),
            len(completed_results),
            len(transitions),
        )

        return MonitoringCycleResult(
            service_results=completed_results,
            transitions=tuple(transitions),
        )

    async def _check_service(
        self,
        service_key: str,
    ) -> ServiceResult | None:
        try:
            return await self._manager.check_service(
                service_key
            )

        except Exception:
            logger.exception(
                "Unexpected failure while checking service",
                extra={
                    "service": service_key,
                    "check": "-",
                },
            )

            return None

    async def _run_loop(self) -> None:
        try:
            while True:
                await self.run_cycle()

                await asyncio.sleep(
                    self._interval_seconds
                )

        except asyncio.CancelledError:
            logger.debug(
                "Monitoring scheduler task cancelled."
            )
            raise

    async def _notify_transition(
        self,
        transition: ServiceTransition,
    ) -> None:
        for notifier in self._notifiers:
            try:
                await notifier.notify(transition)

            except Exception:
                logger.exception(
                    "Transition notifier failed",
                    extra={
                        "service": transition.service_key,
                        "check": "-",
                    },
                )

    async def _persist_service_result(
        self,
        result: ServiceResult,
    ) -> None:
        if self._history_store is None:
            return

        try:
            await self._history_store.append_service_result(
                result
            )

        except Exception:
            logger.exception(
                "Failed to persist service result",
                extra={
                    "service": result.service_key,
                    "check": "-",
                },
            )

            return

        logger.debug(
            "Service result persisted",
            extra={
                "service": result.service_key,
                "check": "-",
            },
        )

    async def _persist_transition(
        self,
        transition: ServiceTransition,
    ) -> None:
        if self._history_store is None:
            return

        try:
            await self._history_store.append_transition(
                transition
            )

        except Exception:
            logger.exception(
                "Failed to persist service transition",
                extra={
                    "service": transition.service_key,
                    "check": "-",
                },
            )

            return

        logger.debug(
            "Service transition persisted",
            extra={
                "service": transition.service_key,
                "check": "-",
            },
        )