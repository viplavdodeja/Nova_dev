"""Robot state definitions for the Nova coordinator."""

from __future__ import annotations

from enum import Enum


class RobotState(str, Enum):
    """Top-level operating states for Nova."""

    OBSERVE = "observe"
    COMMAND_MODE = "command_mode"
    EXECUTING_MOTION = "executing_motion"
    SPEAKING = "speaking"
    PAUSED_FOR_SAFETY = "paused_for_safety"
    ERROR = "error"
