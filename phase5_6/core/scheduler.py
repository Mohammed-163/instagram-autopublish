"""
Scheduler Interface.

No implementation lives here on purpose. The Weekly Planner (and anything
else that needs to schedule future work) should depend on this interface,
not on *how* scheduling actually happens (cron, GitHub Actions, a task
queue, ...). Whichever mechanism gets picked later becomes one concrete
class that implements this interface; nothing that depends on
`SchedulerInterface` has to change when that decision is made.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Optional, Protocol


class Job(Protocol):
    """Whatever the concrete scheduler needs to identify a scheduled unit
    of work. Left intentionally open."""
    id: Any


class SchedulerInterface(ABC):
    """Contract every concrete scheduler implementation must satisfy.

    Not implemented yet — this exists so callers (e.g. a future
    WeeklyPlanner) can be written and tested against this interface today,
    without being coupled to whichever execution mechanism is chosen later.
    """

    @abstractmethod
    def schedule_once(
        self,
        run_at: datetime,
        callback: Callable[..., None],
        *,
        job_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> uuid.UUID:
        """Schedules `callback` to run once at `run_at`. Returns a job id."""
        raise NotImplementedError

    @abstractmethod
    def schedule_recurring(
        self,
        cron_expression: str,
        callback: Callable[..., None],
        *,
        job_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> uuid.UUID:
        """Schedules `callback` to run repeatedly per `cron_expression`."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self, job_id: uuid.UUID) -> bool:
        """Cancels a previously scheduled job. Returns whether it existed."""
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: uuid.UUID) -> Optional[Job]:
        raise NotImplementedError
