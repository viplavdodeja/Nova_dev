"""Transcript parsing helpers for wake phrase and motor commands."""

from __future__ import annotations

import re

from config import (
    BACKWARD_DEFAULT_MS,
    FORWARD_DEFAULT_MS,
    SPIN_360_DEFAULT_MS,
    TURN_LEFT_DEFAULT_MS,
    TURN_RIGHT_DEFAULT_MS,
    U_TURN_DEFAULT_MS,
    WAKE_PHRASE,
)

WAKE_REGEX = re.compile(r"\bhey[\s,!.?-]*nova\b")
DURATION_REGEX = re.compile(
    r"\bfor\s+(?P<value>(?:\d+(?:\.\d+)?)|(?:an?|half|one|two|three|four|five|six|seven|eight|nine|ten))\s+"
    r"(?P<unit>second|seconds|sec|secs|millisecond|milliseconds|ms)\b"
)

NUMBER_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "half": 0.5,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}

COMMAND_PATTERNS = [
    ("look left", ("look left", "LOOK_LEFT", None)),
    ("look right", ("look right", "LOOK_RIGHT", None)),
    ("look forward", ("look forward", "LOOK_CENTER", None)),
    ("center camera", ("center camera", "LOOK_CENTER", None)),
    ("center view", ("center view", "LOOK_CENTER", None)),
    ("u turn left", ("u turn left", "L", U_TURN_DEFAULT_MS)),
    ("u-turn left", ("u turn left", "L", U_TURN_DEFAULT_MS)),
    ("u turn right", ("u turn right", "R", U_TURN_DEFAULT_MS)),
    ("u-turn right", ("u turn right", "R", U_TURN_DEFAULT_MS)),
    ("u turn", ("u turn", "R", U_TURN_DEFAULT_MS)),
    ("u-turn", ("u turn", "R", U_TURN_DEFAULT_MS)),
    ("spin left", ("spin left", "SL", SPIN_360_DEFAULT_MS)),
    ("spin right", ("spin right", "SR", SPIN_360_DEFAULT_MS)),
    ("turn left", ("turn left", "L", TURN_LEFT_DEFAULT_MS)),
    ("left turn", ("turn left", "L", TURN_LEFT_DEFAULT_MS)),
    ("turn right", ("turn right", "R", TURN_RIGHT_DEFAULT_MS)),
    ("right turn", ("turn right", "R", TURN_RIGHT_DEFAULT_MS)),
    ("move forward", ("move forward", "F", FORWARD_DEFAULT_MS)),
    ("go forward", ("go forward", "F", FORWARD_DEFAULT_MS)),
    ("forward", ("forward", "F", FORWARD_DEFAULT_MS)),
    ("move backward", ("move backward", "B", BACKWARD_DEFAULT_MS)),
    ("go backward", ("go backward", "B", BACKWARD_DEFAULT_MS)),
    ("backward", ("backward", "B", BACKWARD_DEFAULT_MS)),
    ("reverse", ("reverse", "B", BACKWARD_DEFAULT_MS)),
    ("back", ("back", "B", BACKWARD_DEFAULT_MS)),
    ("left", ("left", "L", TURN_LEFT_DEFAULT_MS)),
    ("right", ("right", "R", TURN_RIGHT_DEFAULT_MS)),
    ("stop", ("stop", "X", None)),
    ("spin", ("spin", "SR", SPIN_360_DEFAULT_MS)),
]


def normalize_text(text: str) -> str:
    """Normalize transcript for robust keyword matching."""
    lowered = (text or "").strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def contains_wake_phrase(text: str) -> bool:
    """Return True when wake phrase appears in transcript."""
    normalized = normalize_text(text)
    if WAKE_REGEX.search(normalized):
        return True
    return WAKE_PHRASE in normalized


def contains_emergency_stop(text: str) -> bool:
    """Emergency stop is always active in passive mode."""
    normalized = normalize_text(text)
    return "stop" in normalized


def _parse_duration_ms(text: str) -> int | None:
    """Parse a spoken duration phrase like 'for 1 second'."""
    match = DURATION_REGEX.search(text)
    if match is None:
        return None

    raw_value = match.group("value")
    raw_unit = match.group("unit")

    try:
        numeric_value = float(raw_value)
    except ValueError:
        numeric_value = NUMBER_WORDS.get(raw_value)

    if numeric_value is None or numeric_value <= 0:
        return None

    if raw_unit.startswith("ms") or raw_unit.startswith("millisecond"):
        duration_ms = int(numeric_value)
    else:
        duration_ms = int(numeric_value * 1000)

    return duration_ms if duration_ms > 0 else None


def parse_motor_command(text: str) -> tuple[str, str, int | None] | None:
    """Parse transcript and return (matched_phrase, serial_command, duration_ms)."""
    normalized = normalize_text(text)
    if not normalized:
        return None

    spoken_duration_ms = _parse_duration_ms(normalized)

    for phrase, (label, command, default_duration_ms) in COMMAND_PATTERNS:
        if phrase in normalized:
            return label, command, spoken_duration_ms or default_duration_ms
    return None
