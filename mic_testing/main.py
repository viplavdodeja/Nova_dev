"""Continuous microphone transcription test using Whisper."""

from __future__ import annotations

import argparse
import time

import numpy as np
import sounddevice as sd
import whisper

from config import (
    CHANNELS,
    MIC_DEVICE_INDEX,
    RECORD_SECONDS,
    SAMPLE_RATE,
    SILENCE_RMS_THRESHOLD,
    WHISPER_LANGUAGE,
    WHISPER_MODEL_NAME,
    WHISPER_TASK,
)


def parse_args() -> argparse.Namespace:
    """Parse optional CLI overrides."""
    parser = argparse.ArgumentParser(description="Whisper microphone tester")
    parser.add_argument("--model", default=WHISPER_MODEL_NAME, help="Whisper model name")
    parser.add_argument("--seconds", type=float, default=RECORD_SECONDS, help="Recording window per pass")
    parser.add_argument("--device", type=int, default=MIC_DEVICE_INDEX, help="Input device index")
    parser.add_argument("--list-devices", action="store_true", help="Print audio devices and exit")
    return parser.parse_args()


def list_input_devices() -> None:
    """Print available audio devices."""
    devices = sd.query_devices()
    print("Audio devices:")
    for index, device in enumerate(devices):
        max_input = int(device.get("max_input_channels", 0))
        if max_input > 0:
            print(f"  [{index}] {device['name']} (inputs={max_input})")


def record_clip(seconds: float, sample_rate: int, channels: int, device: int | None) -> np.ndarray:
    """Record one audio clip and return mono float32 waveform."""
    frame_count = int(seconds * sample_rate)
    if frame_count <= 0:
        raise ValueError("Recording duration must be positive.")

    audio = sd.rec(
        frame_count,
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        device=device,
    )
    sd.wait()

    waveform = np.squeeze(audio)
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    return waveform.astype(np.float32, copy=False)


def rms_level(waveform: np.ndarray) -> float:
    """Compute RMS loudness for basic silence filtering."""
    if waveform.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(waveform))))


def transcribe_clip(
    model: whisper.Whisper,
    waveform: np.ndarray,
    sample_rate: int,
    language: str,
    task: str,
) -> str:
    """Transcribe one waveform chunk with Whisper."""
    if sample_rate != 16000:
        # Whisper expects 16 kHz audio; keep defaults at 16k for best behavior.
        raise ValueError("Whisper mic test expects SAMPLE_RATE=16000.")

    result = model.transcribe(
        waveform,
        language=language,
        task=task,
        fp16=False,
        temperature=0.0,
    )
    return str(result.get("text", "")).strip()


def run() -> None:
    """Run continuous record/transcribe loop."""
    args = parse_args()

    if args.list_devices:
        list_input_devices()
        return

    print(f"[Whisper] Loading model: {args.model}")
    model = whisper.load_model(args.model)
    print("[Whisper] Ready.")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            print(f"[Mic] Recording {args.seconds:.1f}s...")
            waveform = record_clip(
                seconds=args.seconds,
                sample_rate=SAMPLE_RATE,
                channels=CHANNELS,
                device=args.device,
            )

            level = rms_level(waveform)
            if level < SILENCE_RMS_THRESHOLD:
                print(f"[Mic] Silence/low input (RMS={level:.4f}).")
                continue

            text = transcribe_clip(
                model=model,
                waveform=waveform,
                sample_rate=SAMPLE_RATE,
                language=WHISPER_LANGUAGE,
                task=WHISPER_TASK,
            )
            timestamp = time.strftime("%H:%M:%S")
            if text:
                print(f"[{timestamp}] {text}")
            else:
                print(f"[{timestamp}] (no speech recognized)")
        except KeyboardInterrupt:
            print("\nStopping Whisper mic test.")
            break
        except Exception as exc:
            print(f"[ERROR] {exc}")
            time.sleep(0.5)


if __name__ == "__main__":
    run()
