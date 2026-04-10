"""Text-to-speech service wrapper for Nova responses."""

from __future__ import annotations

from queue import Queue

from events import Event, EventType


class TTSService:
    """Coordinator-facing text-to-speech wrapper."""

    def __init__(self, event_queue: Queue[Event]) -> None:
        self._event_queue = event_queue

    def speak(self, text: str) -> None:
        self._event_queue.put(Event(type=EventType.TTS_STARTED, source="tts", payload={"text": text}))
        self._event_queue.put(Event(type=EventType.TTS_FINISHED, source="tts", payload={"text": text}))
