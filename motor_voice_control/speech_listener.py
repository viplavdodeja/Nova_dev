"""Continuous Vosk-based speech listener for wake and command capture."""

from __future__ import annotations

import json
import queue
import time
from collections import deque
from pathlib import Path

from command_parser import contains_emergency_stop, contains_wake_phrase, normalize_text
from config import (
    COMMAND_LISTEN_TIMEOUT_SECONDS,
    MIC_DEVICE_INDEX,
    STT_BLOCK_SIZE,
    STT_DEBUG,
    STT_SAMPLE_RATE,
    VOSK_MODEL_PATH,
)

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - environment dependent
    sd = None

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except ImportError:  # pragma: no cover - environment dependent
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None


class ContinuousVoskListener:
    """Always-on microphone stream with blocking wake and command helpers."""

    def __init__(self) -> None:
        self._model_path = Path(VOSK_MODEL_PATH)
        self._sample_rate = STT_SAMPLE_RATE
        self._block_size = STT_BLOCK_SIZE
        self._device_index = MIC_DEVICE_INDEX
        self._debug = STT_DEBUG

        self._model: Model | None = None
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=64)
        self._stream = None
        self._started = False

    def validate_environment(self) -> tuple[bool, str]:
        """Validate microphone/STT dependencies and model path."""
        if sd is None:
            return False, "Missing dependency: sounddevice is not installed"
        if Model is None or KaldiRecognizer is None:
            return False, "Missing dependency: vosk is not installed"
        if not self._model_path.exists():
            return False, f"Missing Vosk model path: {self._model_path}"
        return True, ""

    def start(self) -> bool:
        """Start the continuous microphone stream."""
        ok, message = self.validate_environment()
        if not ok:
            print(message)
            return False

        try:
            if SetLogLevel is not None:
                SetLogLevel(-1)
            self._model = Model(str(self._model_path))
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=self._block_size,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
                device=self._device_index,
            )
            self._stream.start()
            self._started = True
            if self._debug:
                print(f"[STT DEBUG] Listening on mic device index: {self._device_index}")
            return True
        except Exception as exc:
            print(f"Audio stream start failure: {exc}")
            self.stop()
            return False

    def stop(self) -> None:
        """Stop the microphone stream and clear buffered audio."""
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        finally:
            self._stream = None
            self._started = False
            self._clear_audio_queue()

    def listen_for_passive_trigger(self) -> str:
        """Block until wake phrase or emergency stop is heard in the live stream."""
        recognizer = self._new_recognizer()
        recent_segments: deque[str] = deque(maxlen=4)

        while self._started:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(chunk):
                text = self._extract_text(recognizer.Result())
                if text:
                    if self._debug:
                        print(f"[STT DEBUG] final: {text}")
                    recent_segments.append(text)
                    combined = normalize_text(" ".join(recent_segments))
                    if contains_emergency_stop(combined) or contains_wake_phrase(combined):
                        return combined
            else:
                partial = self._extract_text(recognizer.PartialResult(), key="partial")
                if partial:
                    if self._debug:
                        print(f"[STT DEBUG] partial: {partial}")
                    combined = normalize_text(" ".join([*recent_segments, partial]))
                    if contains_emergency_stop(combined) or contains_wake_phrase(combined):
                        return combined

        return ""

    def listen_for_command(self, timeout_seconds: float) -> str:
        """Capture rolling command speech from the live stream without reopening audio."""
        recognizer = self._new_recognizer()
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        best_final = ""
        best_partial = ""
        speech_started = False
        last_voice_time = time.monotonic()

        while self._started and time.monotonic() < deadline:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(chunk):
                text = self._extract_text(recognizer.Result())
                if text:
                    if self._debug:
                        print(f"[STT DEBUG] command final: {text}")
                    best_final = text
                    speech_started = True
                    last_voice_time = time.monotonic()
            else:
                partial = self._extract_text(recognizer.PartialResult(), key="partial")
                if partial:
                    if self._debug:
                        print(f"[STT DEBUG] command partial: {partial}")
                    best_partial = partial
                    speech_started = True
                    last_voice_time = time.monotonic()
                elif speech_started and (time.monotonic() - last_voice_time) > 0.6:
                    break

        final_text = self._extract_text(recognizer.FinalResult())
        if final_text:
            best_final = final_text

        return normalize_text(best_final or best_partial)

    def _audio_callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            return
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

    def _new_recognizer(self) -> KaldiRecognizer:
        if self._model is None:
            raise RuntimeError("Speech listener has not been started.")
        return KaldiRecognizer(self._model, self._sample_rate)

    def _clear_audio_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def _extract_text(raw_json: str, key: str = "text") -> str:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            return ""
        return normalize_text(str(parsed.get(key, "")).strip())


def create_listener() -> ContinuousVoskListener:
    """Create and return a live Vosk listener."""
    listener = ContinuousVoskListener()
    if not listener.start():
        raise RuntimeError("Could not start continuous Vosk listener.")
    return listener


def listen_for_command(timeout_seconds: float = COMMAND_LISTEN_TIMEOUT_SECONDS) -> str:
    """Convenience helper for one command capture session."""
    listener = create_listener()
    try:
        return listener.listen_for_command(timeout_seconds)
    finally:
        listener.stop()
