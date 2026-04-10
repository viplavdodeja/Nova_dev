"""Configuration for the Nova integrated runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeConfig:
    """Coordinator-level runtime settings."""

    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 9600
    serial_timeout_seconds: float = 1.0
    camera_index: int = 0
    target_label: str = "person"
    cv_enabled: bool = True
    speech_enabled: bool = True
    tts_enabled: bool = True
    queue_poll_timeout_seconds: float = 0.25
