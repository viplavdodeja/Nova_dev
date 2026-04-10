"""Event definitions for cross-service coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class EventType(str, Enum):
    """Discrete event types passed through the coordinator queue."""

    WAKE_DETECTED = "wake_detected"
    COMMAND_RECEIVED = "command_received"
    EMERGENCY_STOP = "emergency_stop"
    MOTION_STARTED = "motion_started"
    MOTION_COMPLETED = "motion_completed"
    SERVO_COMPLETED = "servo_completed"
    TTS_STARTED = "tts_started"
    TTS_FINISHED = "tts_finished"
    VISION_DETECTION = "vision_detection"
    VISION_TARGET_LOST = "vision_target_lost"
    ERROR = "error"


@dataclass(slots=True)
class Event:
    """Generic event payload exchanged between services and coordinator."""

    type: EventType
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time)
