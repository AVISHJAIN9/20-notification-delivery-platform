"""
Deterministic Clock for Project 20 (Notification Delivery Platform).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


class Clock:
    def __init__(self, initial_time: Optional[datetime] = None, initial_timestamp: Optional[datetime] = None):
        t = initial_time or initial_timestamp or datetime.now(timezone.utc)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        self._current_time = t

    def now(self) -> datetime:
        return self._current_time

    def advance(self, duration: timedelta) -> datetime:
        self._current_time += duration
        return self._current_time

    def set_time(self, new_time: datetime) -> None:
        if new_time.tzinfo is None:
            new_time = new_time.replace(tzinfo=timezone.utc)
        self._current_time = new_time
