"""Very small in-memory event history for demo continuity."""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any


_MAX_EVENTS = 10
_events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_lock = Lock()


def add_event(event_dict: dict[str, Any]) -> None:
    """Store one event in memory."""
    with _lock:
        _events.append(dict(event_dict))


def get_recent_events() -> list[dict[str, Any]]:
    """Return a copy of the most recent events."""
    with _lock:
        return list(_events)
