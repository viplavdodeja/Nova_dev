"""Motion service wrapper for Arduino motor commands."""

from __future__ import annotations

import re
import threading
from queue import Queue

import serial

from config import RuntimeConfig
from events import Event, EventType


class ArduinoSerialClient:
    """Shared serial transport for motion and servo services."""

    def __init__(self, port: str, baud_rate: int, timeout_seconds: float) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._timeout_seconds = timeout_seconds
        self._connection: serial.Serial | None = None

    def connect(self) -> bool:
        try:
            self._connection = serial.Serial(
                port=self._port,
                baudrate=self._baud_rate,
                timeout=self._timeout_seconds,
            )
            print(f"[Serial] Connected to Arduino on {self._port} @ {self._baud_rate}")
            return True
        except Exception as exc:
            print(f"[Serial] Connection error: {exc}")
            self._connection = None
            return False

    def send_message(self, message: str) -> bool:
        if self._connection is None or not self._connection.is_open:
            print("[Serial] Send failed: not connected")
            return False
        payload = (message.strip() + "\n").encode("utf-8")
        try:
            self._connection.write(payload)
            self._connection.flush()
            print(f"[Serial] Sent: {message.strip()}")
            return True
        except Exception as exc:
            print(f"[Serial] Write error: {exc}")
            return False

    def close(self) -> None:
        if self._connection is None:
            return
        try:
            if self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
        finally:
            self._connection = None


class MotionService:
    """Coordinator-facing motion API for calibrated robot actions."""

    def __init__(self, event_queue: Queue[Event], config: RuntimeConfig, serial_client: ArduinoSerialClient) -> None:
        self._event_queue = event_queue
        self._config = config
        self._serial = serial_client
        self._completion_timer: threading.Timer | None = None

    def connect(self) -> bool:
        return self._serial.connect()

    def close(self) -> None:
        if self._completion_timer is not None:
            self._completion_timer.cancel()
            self._completion_timer = None
        self._serial.close()

    def execute(self, action: str) -> None:
        payload = self._config.motion_payloads.get(action)
        if not payload:
            self._event_queue.put(
                Event(type=EventType.ERROR, source="motion", payload={"message": f"Unknown motion action: {action}"})
            )
            return
        self.execute_payload(action, payload)

    def execute_payload(self, action: str, payload: str) -> None:
        """Send an explicit payload and emit motion lifecycle events."""
        if not self._serial.send_message(payload):
            self._event_queue.put(
                Event(type=EventType.ERROR, source="motion", payload={"message": "Serial send failed", "action": action})
            )
            return

        self._event_queue.put(Event(type=EventType.MOTION_STARTED, source="motion", payload={"action": action, "payload": payload}))

        duration_seconds = self._extract_duration_seconds(payload)
        if duration_seconds <= 0:
            self._event_queue.put(Event(type=EventType.MOTION_COMPLETED, source="motion", payload={"action": action}))
            return

        if self._completion_timer is not None:
            self._completion_timer.cancel()
        self._completion_timer = threading.Timer(duration_seconds, self._emit_motion_completed, args=(action,))
        self._completion_timer.daemon = True
        self._completion_timer.start()

    def emergency_stop(self) -> None:
        if self._completion_timer is not None:
            self._completion_timer.cancel()
            self._completion_timer = None
        self._serial.send_message(self._config.motion_payloads["stop"])

    def set_led_state(self, token: str) -> bool:
        return self._serial.send_message(token.strip().upper())

    def send_raw(self, payload: str) -> bool:
        return self._serial.send_message(payload)

    def _emit_motion_completed(self, action: str) -> None:
        self._event_queue.put(Event(type=EventType.MOTION_COMPLETED, source="motion", payload={"action": action}))

    @staticmethod
    def _extract_duration_seconds(payload: str) -> float:
        match = re.search(r"(\d+)$", payload)
        if match is None:
            return 0.0
        return int(match.group(1)) / 1000.0
