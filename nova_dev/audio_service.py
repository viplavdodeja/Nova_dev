"""Audio service wrapper for wake-word and command capture."""

from __future__ import annotations

from queue import Queue

from events import Event, EventType


class AudioService:
    """Thin adapter around the existing speech stack."""

    def __init__(self, event_queue: Queue[Event]) -> None:
        self._event_queue = event_queue
        self._enabled = False

    def start(self) -> None:
        self._enabled = True

    def stop(self) -> None:
        self._enabled = False

    def emit_wake_detected(self) -> None:
        if not self._enabled:
            return
        self._event_queue.put(Event(type=EventType.WAKE_DETECTED, source="audio"))

    def emit_command_received(self, transcript: str) -> None:
        if not self._enabled:
            return
        self._event_queue.put(
            Event(
                type=EventType.COMMAND_RECEIVED,
                source="audio",
                payload={"transcript": transcript},
            )
        )

    def emit_emergency_stop(self, transcript: str = "stop") -> None:
        if not self._enabled:
            return
        self._event_queue.put(
            Event(
                type=EventType.EMERGENCY_STOP,
                source="audio",
                payload={"transcript": transcript},
            )
        )
