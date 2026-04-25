"""Debug utility that prints live microphone transcripts and wake matches."""

from __future__ import annotations

import json
import os
import queue
import sys
from collections import deque
from pathlib import Path

from command_parser import contains_emergency_stop, contains_wake_phrase, normalize_text
from config import WAKE_PHRASE

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


VOSK_MODEL_PATH = Path(os.getenv("NOVA_VOSK_MODEL_PATH", "vosk-model-small-en-us-0.15"))
STT_SAMPLE_RATE = int(os.getenv("NOVA_VOSK_SAMPLE_RATE", "16000"))
STT_BLOCK_SIZE = int(os.getenv("NOVA_VOSK_BLOCK_SIZE", "8000"))
MIC_DEVICE_INDEX = (
    int(os.getenv("NOVA_MIC_DEVICE_INDEX", "").strip())
    if os.getenv("NOVA_MIC_DEVICE_INDEX", "").strip()
    else None
)


def _extract_text(raw_json: str, key: str = "text") -> str:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return ""
    return normalize_text(str(parsed.get(key, "")).strip())


def main() -> None:
    if sd is None:
        print("Missing dependency: sounddevice is not installed")
        return
    if Model is None or KaldiRecognizer is None:
        print("Missing dependency: vosk is not installed")
        return
    if not VOSK_MODEL_PATH.exists():
        print(f"Missing Vosk model path: {VOSK_MODEL_PATH}")
        return

    if SetLogLevel is not None:
        SetLogLevel(-1)

    print("Audio input debug started")
    print(f"Wake phrase target: {WAKE_PHRASE}")
    print(f"Vosk model path: {VOSK_MODEL_PATH}")
    print(f"Mic device index: {MIC_DEVICE_INDEX}")
    print("Printing partial and final transcripts. Press Ctrl+C to stop.\n")

    model = Model(str(VOSK_MODEL_PATH))
    recognizer = KaldiRecognizer(model, STT_SAMPLE_RATE)
    audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=64)
    recent_segments: deque[str] = deque(maxlen=4)

    def _audio_callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
        if status:
            return
        try:
            audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            try:
                audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

    try:
        with sd.RawInputStream(
            samplerate=STT_SAMPLE_RATE,
            blocksize=STT_BLOCK_SIZE,
            dtype="int16",
            channels=1,
            callback=_audio_callback,
            device=MIC_DEVICE_INDEX,
        ):
            while True:
                try:
                    chunk = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(chunk):
                    text = _extract_text(recognizer.Result())
                    if not text:
                        continue
                    recent_segments.append(text)
                    combined = normalize_text(" ".join(recent_segments))
                    wake = contains_wake_phrase(combined)
                    stop = contains_emergency_stop(combined)
                    print(f"[FINAL] {text}")
                    print(f"        combined={combined}")
                    print(f"        wake_match={wake} emergency_stop={stop}")
                else:
                    partial = _extract_text(recognizer.PartialResult(), key="partial")
                    if not partial:
                        continue
                    combined = normalize_text(" ".join([*recent_segments, partial]))
                    wake = contains_wake_phrase(combined)
                    stop = contains_emergency_stop(combined)
                    print(f"[PARTIAL] {partial}")
                    if wake or stop:
                        print(f"          combined={combined}")
                        print(f"          wake_match={wake} emergency_stop={stop}")
    except KeyboardInterrupt:
        print("\nStopping audio input debug")
    except Exception as exc:
        print(f"Audio debug failed: {exc}")


if __name__ == "__main__":
    main()
