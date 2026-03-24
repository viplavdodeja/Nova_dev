"""Offline speech-to-text helpers using Vosk for Raspberry Pi/Linux."""

from __future__ import annotations

import json
import queue
import time

from config import MIC_DEVICE_INDEX, STT_BLOCK_SIZE, STT_LISTEN_TIMEOUT_SECONDS, STT_SAMPLE_RATE, VOSK_MODEL_PATH

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


class STTRecognizer:
    """Container for Vosk model and microphone listen settings."""

    def __init__(
        self,
        model_path: str = VOSK_MODEL_PATH,
        sample_rate: int = STT_SAMPLE_RATE,
        block_size: int = STT_BLOCK_SIZE,
        device_index: int | None = MIC_DEVICE_INDEX,
    ) -> None:
        if sd is None or Model is None or KaldiRecognizer is None:
            raise RuntimeError("vosk/sounddevice dependencies are missing.")
        if SetLogLevel is not None:
            SetLogLevel(-1)
        self.model = Model(model_path)
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.device_index = device_index

    def listen_for_utterance(self, timeout_seconds: float = STT_LISTEN_TIMEOUT_SECONDS) -> str | None:
        """Listen for one utterance and return final text or None."""
        audio_queue: queue.Queue[bytes] = queue.Queue()
        recognizer = KaldiRecognizer(self.model, self.sample_rate)
        start_time = time.time()
        partial_text = ""

        def _audio_callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
            if status:
                return
            audio_queue.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="int16",
                channels=1,
                callback=_audio_callback,
                device=self.device_index,
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
            print(f"[STT] Microphone/STT failure: {exc}")
            return None

        final_result = json.loads(recognizer.FinalResult())
        final_text = str(final_result.get("text", "")).strip()
        if final_text:
            return final_text
        return partial_text or None


def create_recognizer() -> STTRecognizer:
    """Create and return an STTRecognizer instance."""
    return STTRecognizer()


def listen_for_utterance(recognizer: STTRecognizer | None = None) -> str | None:
    """Convenience wrapper that listens for one utterance."""
    active = recognizer or create_recognizer()
    return active.listen_for_utterance()

