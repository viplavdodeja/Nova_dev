"""Transcript parsing helpers for wake phrase and motor commands."""

from __future__ import annotations

import re

from config import WAKE_PHRASE


def normalize_text(text: str) -> str:
    """Normalize transcript for robust keyword matching."""
    lowered = (text or "").strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def contains_wake_phrase(text: str) -> bool:
    """Return True when wake phrase appears in transcript."""
    normalized = normalize_text(text)
    return WAKE_PHRASE in normalized


def contains_emergency_stop(text: str) -> bool:
    """Emergency stop is always active in passive mode."""
    normalized = normalize_text(text)
    return "stop" in normalized


def parse_motor_command(text: str) -> tuple[str, str] | None:
    """Parse transcript and return (matched_phrase, serial_letter)."""
    normalized = normalize_text(text)
    if not normalized:
        return None

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
            return phrase, letter
    return None
