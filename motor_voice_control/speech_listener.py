"""Whisper-based speech listener compatibility layer for motor voice control."""

from __future__ import annotations

from command_parser import normalize_text
from config import COMMAND_LISTEN_TIMEOUT_SECONDS
from speech_listener_whisper_cpp import WhisperCppListener


class WhisperSpeechListener:
    """Compatibility wrapper exposing the old listener API on top of whisper.cpp clips."""

    def __init__(self) -> None:
        self._listener = WhisperCppListener()
        self._started = False

    def validate_environment(self) -> tuple[bool, str]:
        return self._listener.validate_environment()

    def start(self) -> bool:
        ok, message = self.validate_environment()
        if not ok:
            print(message)
            return False
        self._started = True
        return True

    def stop(self) -> None:
        self._started = False

    def listen_for_passive_trigger(self) -> str:
        if not self._started:
            raise RuntimeError("Speech listener has not been started.")
        return normalize_text(
            self._listener.listen_once(
                self._listener.passive_duration_seconds(),
                command_mode=False,
            )
        )

    def listen_for_command(self, timeout_seconds: float) -> str:
        if not self._started:
            raise RuntimeError("Speech listener has not been started.")
        duration_seconds = max(float(timeout_seconds), self._listener.command_duration_seconds())
        return normalize_text(
            self._listener.listen_once(
                duration_seconds,
                command_mode=True,
            )
        )


ContinuousVoskListener = WhisperSpeechListener


def create_listener() -> WhisperSpeechListener:
    """Create and return a listener using whisper.cpp clip transcription."""
    listener = WhisperSpeechListener()
    if not listener.start():
        raise RuntimeError("Could not start whisper speech listener.")
    return listener


def listen_for_command(timeout_seconds: float = COMMAND_LISTEN_TIMEOUT_SECONDS) -> str:
    """Convenience helper for one command capture session."""
    listener = create_listener()
    try:
        return listener.listen_for_command(timeout_seconds)
    finally:
        listener.stop()
