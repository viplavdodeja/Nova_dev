"""Servo service wrapper for camera pan control."""

from __future__ import annotations

from queue import Queue

from events import Event, EventType


class ServoService:
    """Coordinator-facing camera servo wrapper."""

    def __init__(self, event_queue: Queue[Event]) -> None:
        self._event_queue = event_queue
        self._current_angle = 90

    @property
    def current_angle(self) -> int:
        return self._current_angle

    def set_angle(self, angle: int) -> None:
        self._current_angle = angle
        self._event_queue.put(
            Event(type=EventType.SERVO_COMPLETED, source="servo", payload={"angle": angle})
        )
