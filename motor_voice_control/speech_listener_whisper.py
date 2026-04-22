"""Whisper-based speech listener for wake phrase and command capture."""

from __future__ import annotations

import time

import numpy as np

from command_parser import contains_emergency_stop, contains_wake_phrase, normalize_text
from config import (
    MIC_DEVICE_INDEX,
    STT_SAMPLE_RATE,
    WHISPER_INITIAL_PROMPT,
    WHISPER_LANGUAGE,
    WHISPER_MODEL_NAME,
    WHISPER_WAKE_RECORD_SECONDS,
    WHISPER_SILENCE_RMS_THRESHOLD,
    WHISPER_TASK,
)

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - environment dependent
    sd = None

try:
    import whisper
except ImportError:  # pragma: no cover - environment dependent
    whisper = None


class WhisperSpeechListener:
    """Record short clips and transcribe them with Whisper."""

    def __init__(self) -> None:
        self._model_name = WHISPER_MODEL_NAME
        self._device_index = MIC_DEVICE_INDEX
        self._target_sample_rate = STT_SAMPLE_RATE
        self._wake_record_seconds = WHISPER_WAKE_RECORD_SECONDS
        self._model = None
        self._started = False

    def validate_environment(self) -> tuple[bool, str]:
        """Validate microphone/STT dependencies."""
        if sd is None:
            return False, "Missing dependency: sounddevice is not installed"
        if whisper is None:
            return False, "Missing dependency: openai-whisper is not installed"
        return True, ""

    def start(self) -> bool:
        """Load Whisper model and prepare for clip-based recognition."""
        ok, message = self.validate_environment()
        if not ok:
            print(message)
            return False

        try:
            print(f"[Whisper] Loading model: {self._model_name}")
            self._model = whisper.load_model(self._model_name)
            self._started = True
            print("[Whisper] Ready.")
            print(f"[Mic] Input device index: {self._device_index}")
            return True
        except Exception as exc:
            print(f"Whisper start failure: {exc}")
            self.stop()
            return False

    def stop(self) -> None:
        """Mark listener stopped."""
        self._started = False

    def listen_for_passive_trigger(self) -> str:
        """Block until wake phrase or emergency stop is heard."""
        while self._started:
            text = normalize_text(self._listen_once(self._wake_record_seconds))
            if text:
                print(f"[Whisper] Heard: {text}")
            if contains_emergency_stop(text) or contains_wake_phrase(text):
                return text
        return ""

    def listen_for_command(self, timeout_seconds: float) -> str:
        """Capture one command phrase after wake detection."""
        return normalize_text(self._listen_once(max(timeout_seconds, 0.5)))

    def _listen_once(self, seconds: float) -> str:
        if self._model is None:
            return ""

        try:
            input_sample_rate = self._resolve_input_sample_rate()
            waveform = self._record_clip(seconds=seconds, sample_rate=input_sample_rate)
            whisper_waveform = self._resample_waveform(
                waveform=waveform,
                src_rate=input_sample_rate,
                dst_rate=self._target_sample_rate,
            )

            if self._rms_level(whisper_waveform) < WHISPER_SILENCE_RMS_THRESHOLD:
                return ""

            result = self._model.transcribe(
                whisper_waveform,
                language=WHISPER_LANGUAGE,
                task=WHISPER_TASK,
                fp16=False,
                temperature=0.0,
                initial_prompt=WHISPER_INITIAL_PROMPT,
                condition_on_previous_text=False,
            )
            return str(result.get("text", "")).strip()
        except Exception as exc:
            print(f"[Whisper] Microphone/STT failure: {exc}")
            time.sleep(0.5)
            return ""

    def _resolve_input_sample_rate(self) -> int:
        if self._device_index is None:
            default_device = sd.default.device
            input_index = default_device[0] if isinstance(default_device, (list, tuple)) else default_device
        else:
            input_index = self._device_index

        info = sd.query_devices(input_index, "input")
        default_sr = int(round(float(info.get("default_samplerate", 0.0))))
        return default_sr if default_sr > 0 else self._target_sample_rate

    def _record_clip(self, seconds: float, sample_rate: int) -> np.ndarray:
        frame_count = int(seconds * sample_rate)
        audio = sd.rec(
            frame_count,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=self._device_index,
        )
        sd.wait()
        waveform = np.squeeze(audio)
        if waveform.ndim > 1:
            waveform = waveform.mean(axis=1)
        return waveform.astype(np.float32, copy=False)

    @staticmethod
    def _resample_waveform(waveform: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        if src_rate == dst_rate or waveform.size == 0:
            return waveform.astype(np.float32, copy=False)

        src_len = waveform.shape[0]
        dst_len = int(round(src_len * float(dst_rate) / float(src_rate)))
        if dst_len <= 1:
            return waveform.astype(np.float32, copy=False)

        src_x = np.linspace(0.0, 1.0, num=src_len, endpoint=True)
        dst_x = np.linspace(0.0, 1.0, num=dst_len, endpoint=True)
        return np.interp(dst_x, src_x, waveform).astype(np.float32, copy=False)

    @staticmethod
    def _rms_level(waveform: np.ndarray) -> float:
        if waveform.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(waveform))))
