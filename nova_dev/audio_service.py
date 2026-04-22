"""Audio service wrapper for wake-word and command capture."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import re
import time
from queue import Queue

from config import RuntimeConfig
from events import Event, EventType

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


WAKE_REGEX = re.compile(r"\bnova\b")


def normalize_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    return re.sub(r"\s+", " ", lowered)


class AudioService:
    """Vosk-backed wake phrase and command capture service."""

    def __init__(self, event_queue: Queue[Event], config: RuntimeConfig) -> None:
        self._event_queue = event_queue
        self._config = config
        self._model_path = self._resolve_model_path(config.vosk_model_path)
        self._model = None
        self._enabled = False

    def start(self) -> None:
        if sd is None or Model is None or KaldiRecognizer is None:
            raise RuntimeError("vosk/sounddevice dependencies are missing.")
        missing_reason = self._model_path_error()
        if missing_reason is not None:
            raise RuntimeError(missing_reason)
        if SetLogLevel is not None:
            SetLogLevel(-1)
        self._model = Model(str(self._model_path))
        self._enabled = True

    def stop(self) -> None:
        self._enabled = False

    def poll_passive(self) -> None:
        """Listen briefly and emit wake/emergency events if detected."""
        if not self._enabled:
            return
        transcript = self._listen_once(self._config.passive_listen_timeout_seconds)
        normalized = normalize_text(transcript or "")
        if not normalized:
            return
        print(f"[Audio] Heard (passive): {normalized}")
        if "stop" in normalized:
            self._event_queue.put(
                Event(type=EventType.EMERGENCY_STOP, source="audio", payload={"transcript": normalized})
            )
            return
        if WAKE_REGEX.search(normalized) or self._config.wake_phrase in normalized:
            self._event_queue.put(
                Event(type=EventType.WAKE_DETECTED, source="audio", payload={"transcript": normalized})
            )

    def capture_command(self) -> None:
        """Listen once in command mode and emit a command event."""
        if not self._enabled:
            return
        transcript = self._listen_once(self._config.command_listen_timeout_seconds)
        normalized = normalize_text(transcript or "")
        if not normalized:
            return
        print(f"[Audio] Heard (command): {normalized}")
        self._event_queue.put(
            Event(type=EventType.COMMAND_RECEIVED, source="audio", payload={"transcript": normalized})
        )

    def _listen_once(self, timeout_seconds: float) -> str | None:
        audio_queue: queue.Queue[bytes] = queue.Queue()
        recognizer = KaldiRecognizer(self._model, self._config.stt_sample_rate)
        start_time = time.time()
        partial_text = ""

        def _audio_callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
            if status:
                return
            audio_queue.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self._config.stt_sample_rate,
                blocksize=self._config.stt_block_size,
                dtype="int16",
                channels=1,
                callback=_audio_callback,
                device=self._config.mic_device_index,
            ):
                while time.time() - start_time < timeout_seconds:
                    try:
                        chunk = audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if recognizer.AcceptWaveform(chunk):
                        result = json.loads(recognizer.Result())
                        text = str(result.get("text", "")).strip()
                        if text:
                            return text
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "")
                        partial_text = str(partial).strip() or partial_text
        except Exception as exc:
            print(f"[Audio] Microphone/STT failure: {exc}")
            return None

        final_result = json.loads(recognizer.FinalResult())
        final_text = str(final_result.get("text", "")).strip()
        return final_text or partial_text or None

    @staticmethod
    def _resolve_model_path(configured_path: str) -> Path:
        candidate = Path(configured_path).expanduser()
        if candidate.is_absolute():
            return candidate
        service_dir = Path(__file__).resolve().parent
        return (service_dir / candidate).resolve()

    def _model_path_error(self) -> str | None:
        if not self._model_path.exists():
            return (
                f"Missing Vosk model path: {self._model_path}. "
                "Set NOVA_VOSK_MODEL_PATH to the extracted Vosk model directory."
            )
        if not self._model_path.is_dir():
            return f"Vosk model path is not a directory: {self._model_path}"
        required_entries = ("am", "conf", "graph", "ivector")
        missing_entries = [name for name in required_entries if not (self._model_path / name).exists()]
        if missing_entries:
            return (
                f"Vosk model folder is incomplete: {self._model_path}. "
                f"Missing expected entries: {', '.join(missing_entries)}"
            )
        return None
