"""Transcript parsing helpers for wake phrase and motor commands."""

from __future__ import annotations

import re

from config import (
    BACKWARD_DEFAULT_MS,
    BACKWARD_DISTANCE_CALIBRATION_IN,
    FORWARD_DEFAULT_MS,
    FORWARD_DISTANCE_CALIBRATION_IN,
    GREETING_COMMANDS,
    SPIN_360_DEFAULT_MS,
    TURN_LEFT_DEFAULT_MS,
    TURN_RIGHT_DEFAULT_MS,
    U_TURN_DEFAULT_MS,
    WAKE_PHRASE,
)

WAKE_REGEX = re.compile(r"\bnova\b")
DURATION_REGEX = re.compile(
    r"\bfor\s+(?P<value>(?:\d+(?:\.\d+)?)|(?:an?|half|one|two|three|four|five|six|seven|eight|nine|ten))\s+"
    r"(?P<unit>second|seconds|sec|secs|millisecond|milliseconds|ms)\b"
)
DISTANCE_REGEX = re.compile(
    r"\b(?:(?:for|move|go)\s+)?(?P<value>(?:\d+(?:\.\d+)?)|(?:an?|half|one|two|three|four|five|six|seven|eight|nine|ten))\s+"
    r"(?P<unit>centimeter|centimeters|centimetre|centimetres|cm|inch|inches|in|foot|feet|ft)\b"
)
BARE_DURATION_UNIT_REGEX = re.compile(r"\b(?:second|seconds|sec|secs|millisecond|milliseconds|ms)\b")

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


def parse_greeting_command(text: str) -> str | None:
    """Return the matched greeting phrase when the transcript is a greeting."""
    normalized = normalize_text(text)
    if not normalized:
        return None

    for greeting in GREETING_COMMANDS:
        if greeting in normalized:
            return greeting
    return None


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


def _distance_to_cm(value: float, unit: str) -> float:
    normalized_unit = unit.strip().lower()
    if normalized_unit in {"inch", "inches", "in"}:
        return value * 2.54
    return value


def _distance_to_inches(value: float, unit: str) -> float:
    normalized_unit = unit.strip().lower()
    if normalized_unit in {"inch", "inches", "in"}:
        return value
    if normalized_unit in {"foot", "feet", "ft"}:
        return value * 12.0
    return value / 2.54


def _interpolate_duration(distance_in: float, calibration_table: list[tuple[float, int]]) -> int | None:
    """Map distance in inches to duration via linear interpolation."""
    if not calibration_table:
        return None

    table = sorted(calibration_table, key=lambda item: item[0])

    if distance_in <= table[0][0]:
        return int(table[0][1])

    if distance_in >= table[-1][0]:
        return int(table[-1][1])

    for index in range(len(table) - 1):
        d1, t1 = table[index]
        d2, t2 = table[index + 1]
        if d1 <= distance_in <= d2:
            if d2 == d1:
                return int(t1)
            ratio = (distance_in - d1) / (d2 - d1)
            return int(t1 + ratio * (t2 - t1))

    return None


def _parse_distance_duration(text: str, command: str) -> int | None:
    """Parse spoken distance like 'forward 10 cm' or 'backward 4 inches'."""
    match = DISTANCE_REGEX.search(text)
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

    distance_in = _distance_to_inches(numeric_value, raw_unit)
    if command == "F":
        return _interpolate_duration(distance_in, FORWARD_DISTANCE_CALIBRATION_IN)
    if command == "B":
        return _interpolate_duration(distance_in, BACKWARD_DISTANCE_CALIBRATION_IN)
    return None


def parse_motor_command(text: str) -> tuple[str, str, int | None] | None:
    """Parse transcript and return (matched_phrase, serial_command, duration_ms)."""
    normalized = normalize_text(text)
    if not normalized:
        return None

    spoken_duration_ms = _parse_duration_ms(normalized)
    has_unparsed_duration_unit = spoken_duration_ms is None and BARE_DURATION_UNIT_REGEX.search(normalized) is not None

    for phrase, (label, command, default_duration_ms) in COMMAND_PATTERNS:
        if phrase in normalized:
            if has_unparsed_duration_unit and command in {"F", "B", "L", "R", "SL", "SR"}:
                return None
            duration_ms = default_duration_ms
            spoken_distance_ms = _parse_distance_duration(normalized, command)
            if command in {"F", "B"} and spoken_distance_ms is not None:
                duration_ms = spoken_distance_ms
            elif spoken_duration_ms is not None:
                duration_ms = spoken_duration_ms
            return label, command, duration_ms
    return None
