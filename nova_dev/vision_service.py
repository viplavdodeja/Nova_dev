"""Vision service wrapper for camera capture and inference."""

from __future__ import annotations

from queue import Queue

from events import Event, EventType


class VisionService:
    """Stateful wrapper for CV activity control."""

    def __init__(self, event_queue: Queue[Event]) -> None:
        self._event_queue = event_queue
        self._capture_enabled = False
        self._inference_enabled = False

    def start(self) -> None:
        self._capture_enabled = True
        self._inference_enabled = True

    def stop(self) -> None:
        self._capture_enabled = False
        self._inference_enabled = False

    def pause_inference(self) -> None:
        self._inference_enabled = False

    def resume_inference(self) -> None:
        self._inference_enabled = True

    @property
    def inference_enabled(self) -> bool:
        return self._inference_enabled

    def emit_detection(self, label: str, confidence: float, extra: dict | None = None) -> None:
        if not (self._capture_enabled and self._inference_enabled):
            return
        payload = {"label": label, "confidence": confidence}
        if extra:
            payload.update(extra)
        self._event_queue.put(Event(type=EventType.VISION_DETECTION, source="vision", payload=payload))

    def emit_target_lost(self) -> None:
        if not self._capture_enabled:
            return
        self._event_queue.put(Event(type=EventType.VISION_TARGET_LOST, source="vision"))
