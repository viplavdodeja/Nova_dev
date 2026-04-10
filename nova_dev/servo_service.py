"""Servo service wrapper for camera pan control."""

from __future__ import annotations

from queue import Queue

from config import RuntimeConfig
from events import Event, EventType
from motion_service import ArduinoSerialClient


class ServoService:
    """Coordinator-facing camera servo wrapper."""

    def __init__(self, event_queue: Queue[Event], config: RuntimeConfig, serial_client: ArduinoSerialClient) -> None:
        self._event_queue = event_queue
        self._config = config
        self._serial = serial_client
        self._current_angle = config.servo_angles["look_center"]

    @property
    def current_angle(self) -> int:
        return self._current_angle

    def look_left(self) -> None:
        self.set_angle(self._config.servo_angles["look_left"])

    def look_center(self) -> None:
        self.set_angle(self._config.servo_angles["look_center"])

    def look_right(self) -> None:
        self.set_angle(self._config.servo_angles["look_right"])

    def set_angle(self, angle: int) -> None:
        self._current_angle = angle
        if self._serial.send_message(f"SV{angle}"):
            self._event_queue.put(Event(type=EventType.SERVO_COMPLETED, source="servo", payload={"angle": angle}))
        else:
            self._event_queue.put(
                Event(type=EventType.ERROR, source="servo", payload={"message": "Serial send failed", "angle": angle})
            )
