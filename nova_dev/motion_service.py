"""Motion service wrapper for Arduino motor commands."""

from __future__ import annotations

from queue import Queue

from events import Event, EventType


class MotionService:
    """Coordinator-facing motion API for calibrated robot actions."""

    def __init__(self, event_queue: Queue[Event]) -> None:
        self._event_queue = event_queue
        self._active_action: str | None = None

    def execute(self, action: str) -> None:
        self._active_action = action
        self._event_queue.put(
            Event(type=EventType.MOTION_STARTED, source="motion", payload={"action": action})
        )

    def complete(self, action: str | None = None) -> None:
        finished_action = action or self._active_action or "unknown"
        self._active_action = None
        self._event_queue.put(
            Event(type=EventType.MOTION_COMPLETED, source="motion", payload={"action": finished_action})
        )

    def emergency_stop(self) -> None:
        self._active_action = None
        self._event_queue.put(
            Event(type=EventType.EMERGENCY_STOP, source="motion", payload={"reason": "requested"})
        )
