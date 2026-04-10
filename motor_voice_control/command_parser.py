"""Transcript parsing helpers for wake phrase and motor commands."""

from __future__ import annotations

import re

from config import WAKE_PHRASE

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
    """Parse transcript and return (matched_phrase, serial_letter, duration_ms)."""
    normalized = normalize_text(text)
    if not normalized:
        return None

    duration_ms = _parse_duration_ms(normalized)

    checks = [
        ("forward", "F"),
        ("backward", "B"),
        ("reverse", "B"),
        ("back", "B"),
        ("left", "L"),
        ("right", "R"),
        ("stop", "X"),
        ("spin", "S"),
    ]
    for phrase, letter in checks:
        if phrase in normalized:
            return phrase, letter, duration_ms
    return None
