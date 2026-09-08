"""
Background Scheduler for Periodic Global Data Ingestion.
Runs non-blocking periodic polling of Open-Meteo, FIRMS, USGS, and GDACS feeds.
"""

import asyncio
from typing import Optional
from intelligence.core.logging import get_logger
from intelligence.external_data.service import get_external_data_service

logger = get_logger("external_scheduler")


class ExternalDataScheduler:
    """Manages asynchronous periodic polling of external environmental data feeds."""

    def __init__(self, interval_seconds: float = 600.0):
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"ExternalDataScheduler started with interval={self.interval_seconds}s")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ExternalDataScheduler stopped")

    async def _run_loop(self) -> None:
        service = get_external_data_service()
        # Initial sync on startup in background thread to avoid blocking server boot
        try:
            await asyncio.to_thread(service.sync_all_feeds, False)
        except Exception as e:
            logger.warning(f"Initial global feed sync note: {e}")

        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                if not self._running:
                    break
                await asyncio.to_thread(service.sync_all_feeds, False)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Periodic global feed sync encountered error: {exc}")
                await asyncio.sleep(30.0)


_scheduler_instance: Optional[ExternalDataScheduler] = None


def get_external_data_scheduler() -> ExternalDataScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ExternalDataScheduler(interval_seconds=600.0)
    return _scheduler_instance
