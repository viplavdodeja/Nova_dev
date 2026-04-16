"""Serial communication layer for sending motor commands to Arduino."""

from __future__ import annotations

from pathlib import Path

import serial
from serial.tools import list_ports


class MotorController:
    """Small wrapper around pyserial for one-letter motor commands."""

    def __init__(self, port: str, baud_rate: int, timeout_seconds: float) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._timeout_seconds = timeout_seconds
        self._serial_connection: serial.Serial | None = None

    def _candidate_ports(self) -> list[str]:
        """Return ordered serial port candidates for Linux SBC setups."""
        configured = self._port.strip()
        candidates: list[str] = []

        if configured and configured.lower() != "auto":
            candidates.append(configured)

        discovered = sorted(
            port.device
            for port in list_ports.comports()
            if port.device.startswith("/dev/ttyUSB")
            or port.device.startswith("/dev/ttyACM")
            or port.device.startswith("/dev/serial/by-id/")
        )

        for device in discovered:
            if device not in candidates:
                candidates.append(device)

        fallback_patterns = (
            "/dev/serial/by-id/*",
            "/dev/ttyACM*",
            "/dev/ttyUSB*",
        )
        for pattern in fallback_patterns:
            for path in sorted(Path("/").glob(pattern.lstrip("/"))):
                device = str(path)
                if device not in candidates:
                    candidates.append(device)

        return candidates

    def connect(self) -> bool:
        """Open serial connection; return True on success."""
        candidates = self._candidate_ports()
        if not candidates:
            print(
                "Serial connection error: no candidate ports found. "
                "Check `ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null` "
                "or set NOVA_SERIAL_PORT explicitly."
            )
            self._serial_connection = None
            return False

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                self._serial_connection = serial.Serial(
                    port=candidate,
                    baudrate=self._baud_rate,
                    timeout=self._timeout_seconds,
                )
                self._port = candidate
                print(f"Connected to Arduino on {candidate} @ {self._baud_rate}")
                return True
            except Exception as exc:
                last_error = exc

        print(
            "Serial connection error: could not open any detected port "
            f"{candidates}. Last error: {last_error}"
        )
        self._serial_connection = None
        return False

    def send_command(self, letter: str) -> bool:
        """Send a single-letter command over serial."""
        command = letter.strip().upper()[:1]
        return self.send_message(command)

    def send_message(self, message: str) -> bool:
        """Send an arbitrary serial line message."""
        if self._serial_connection is None or not self._serial_connection.is_open:
            print("Serial send failed: not connected")
            return False

        payload = (message.strip() + "\n").encode("utf-8")
        try:
            self._serial_connection.write(payload)
            self._serial_connection.flush()
            print(f"Sent to Arduino: {message.strip()}")
            return True
        except Exception as exc:
            print(f"Serial write error: {exc}")
            return False

    def set_led_state(self, led_state: str) -> bool:
        """Send LED state token to Arduino."""
        return self.send_message(led_state.strip().upper())

    def close(self) -> None:
        """Close serial connection when done."""
        if self._serial_connection is None:
            return
        try:
            if self._serial_connection.is_open:
                self._serial_connection.close()
        except Exception:
            pass
        finally:
            self._serial_connection = None
