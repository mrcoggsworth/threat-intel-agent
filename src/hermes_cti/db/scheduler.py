"""Dedicated scheduler process for the independent daily pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hermes_cti.core.settings import Settings
from hermes_cti.db.pipeline import DailyPipeline
from hermes_cti.models.contracts import SourceRegistry

Sleep = Callable[[float], Awaitable[None]]


class DailyScheduler:
    """Calculate a timezone-aware daily schedule and invoke the pipeline."""

    def __init__(
        self,
        settings: Settings,
        pipeline: DailyPipeline,
        registry: SourceRegistry,
        *,
        clock: Callable[[], datetime] | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self.settings = settings
        self.pipeline = pipeline
        self.registry = registry
        self.zone = ZoneInfo(settings.schedule_timezone)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep or asyncio.sleep

    def _local(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduler clock must return an aware datetime")
        return value.astimezone(self.zone)

    def scheduled_for(self, now: datetime) -> datetime:
        """Return the most recent scheduled instant that is due for ``now``."""

        local_now = self._local(now)
        target = datetime.combine(
            local_now.date(),
            time(hour=self.settings.schedule_hour),
            tzinfo=self.zone,
        )
        if local_now < target:
            target -= timedelta(days=1)
        return target.astimezone(UTC)

    def next_scheduled_for(self, now: datetime) -> datetime:
        local_now = self._local(now)
        target = datetime.combine(
            local_now.date(),
            time(hour=self.settings.schedule_hour),
            tzinfo=self.zone,
        )
        if local_now >= target:
            target += timedelta(days=1)
        return target.astimezone(UTC)

    async def run_once(self, now: datetime | None = None) -> None:
        scheduled = self.scheduled_for(now or self._clock())
        await self.pipeline.run_once(self.registry, scheduled_for=scheduled)

    async def run_forever(self) -> None:
        """Keep scheduling independent of web workers or host cron."""

        # Stable idempotency makes restart catch-up safe.
        await self.run_once(self._clock())

        while True:
            now = self._clock()
            next_run = self.next_scheduled_for(now)
            await self._sleep(
                max(1.0, (next_run - now.astimezone(UTC)).total_seconds())
            )
            await self.run_once(self._clock())
