"""Serial communication layer for sending motor commands to Arduino."""

from __future__ import annotations

import serial


class MotorController:
    """Small wrapper around pyserial for one-letter motor commands."""

    def __init__(self, port: str, baud_rate: int, timeout_seconds: float) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._timeout_seconds = timeout_seconds
        self._serial_connection: serial.Serial | None = None

    def connect(self) -> bool:
        """Open serial connection; return True on success."""
        try:
            self._serial_connection = serial.Serial(
                port=self._port,
                baudrate=self._baud_rate,
                timeout=self._timeout_seconds,
            )
            print(f"Connected to Arduino on {self._port} @ {self._baud_rate}")
            return True
        except Exception as exc:
            print(f"Serial connection error: {exc}")
            self._serial_connection = None
            return False

    def send_command(self, letter: str) -> bool:
        """Send a single-letter command over serial."""
        if self._serial_connection is None or not self._serial_connection.is_open:
            print("Serial send failed: not connected")
            return False

        payload = (letter.strip().upper()[:1] + "\n").encode("utf-8")
        try:
            self._serial_connection.write(payload)
            self._serial_connection.flush()
            print(f"Sent to Arduino: {letter.strip().upper()[:1]}")
            return True
        except Exception as exc:
            print(f"Serial write error: {exc}")
            return False

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
