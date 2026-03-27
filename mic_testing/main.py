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
    SILENCE_RMS_THRESHOLD,
    TARGET_SAMPLE_RATE,
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
            default_sr = float(device.get("default_samplerate", 0.0))
            print(f"  [{index}] {device['name']} (inputs={max_input}, default_sr={default_sr:.0f})")


def resolve_input_sample_rate(device: int | None) -> int:
    """Resolve a likely-valid input sample rate for the chosen device."""
    if device is None:
        default_device = sd.default.device
        input_index = default_device[0] if isinstance(default_device, (list, tuple)) else default_device
    else:
        input_index = device

    info = sd.query_devices(input_index, "input")
    default_sr = int(round(float(info.get("default_samplerate", 0.0))))
    if default_sr <= 0:
        return TARGET_SAMPLE_RATE
    return default_sr


def resample_waveform(waveform: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample 1D waveform using linear interpolation."""
    if src_rate == dst_rate or waveform.size == 0:
        return waveform.astype(np.float32, copy=False)

    src_len = waveform.shape[0]
    dst_len = int(round(src_len * float(dst_rate) / float(src_rate)))
    if dst_len <= 1:
        return waveform.astype(np.float32, copy=False)

    src_x = np.linspace(0.0, 1.0, num=src_len, endpoint=True)
    dst_x = np.linspace(0.0, 1.0, num=dst_len, endpoint=True)
    out = np.interp(dst_x, src_x, waveform).astype(np.float32, copy=False)
    return out


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
    input_sample_rate = resolve_input_sample_rate(args.device)
    print(f"[Mic] Using input sample rate: {input_sample_rate} Hz")
    print(f"[Whisper] Target sample rate: {TARGET_SAMPLE_RATE} Hz")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            print(f"[Mic] Recording {args.seconds:.1f}s...")
            waveform = record_clip(
                seconds=args.seconds,
                sample_rate=input_sample_rate,
                channels=CHANNELS,
                device=args.device,
            )
            whisper_waveform = resample_waveform(
                waveform=waveform,
                src_rate=input_sample_rate,
                dst_rate=TARGET_SAMPLE_RATE,
            )

            level = rms_level(whisper_waveform)
            if level < SILENCE_RMS_THRESHOLD:
                print(f"[Mic] Silence/low input (RMS={level:.4f}).")
                continue

            text = transcribe_clip(
                model=model,
                waveform=whisper_waveform,
                sample_rate=TARGET_SAMPLE_RATE,
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
