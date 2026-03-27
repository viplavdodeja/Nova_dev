"""Speech output using Piper with in-memory playback (no temp WAV files)."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path
from urllib import request

import numpy as np

from config import (
    ENABLE_TTS_FALLBACK_ESPEAK,
    PIPER_COMMAND,
    PIPER_HTTP_TIMEOUT_SECONDS,
    PIPER_HTTP_URL,
    PIPER_MODEL_PATH,
    PIPER_SAMPLE_RATE,
    PIPER_VOICE,
)

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - environment dependent
    sd = None


def _sanitize_text(text: str) -> str:
    """Return speech text cleaned for stable TTS behavior."""
    safe = re.sub(r"[\x00-\x1F\x7F]", " ", text)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:500]


def _play_pcm_int16(raw_bytes: bytes, sample_rate: int) -> bool:
    """Play 16-bit PCM audio bytes directly from memory."""
    if not raw_bytes:
        return False
    if sd is None:
        print("[TTS] sounddevice is not installed.")
        return False
    try:
        audio = np.frombuffer(raw_bytes, dtype=np.int16)
        if audio.size == 0:
            return False
        sd.play(audio, samplerate=sample_rate, blocking=True)
        return True
    except Exception as exc:
        print(f"[TTS] PCM playback failed: {exc}")
        return False


def _play_wav_bytes(wav_bytes: bytes) -> bool:
    """Decode WAV in memory and play it via sounddevice."""
    if not wav_bytes or not wav_bytes.startswith(b"RIFF"):
        return False
    if sd is None:
        print("[TTS] sounddevice is not installed.")
        return False

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            frames = reader.readframes(reader.getnframes())

        if sample_width != 2:
            print(f"[TTS] Unsupported WAV sample width: {sample_width}")
            return False

        audio = np.frombuffer(frames, dtype=np.int16)
        if channels > 1:
            audio = audio.reshape(-1, channels)
        sd.play(audio, samplerate=sample_rate, blocking=True)
        return True
    except Exception as exc:
        print(f"[TTS] WAV playback failed: {exc}")
        return False


def _http_post(url: str, payload: bytes, content_type: str) -> bytes | None:
    """Send POST request and return raw bytes, or None on failure."""
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": content_type},
    )
    try:
        with request.urlopen(req, timeout=PIPER_HTTP_TIMEOUT_SECONDS) as response:
            return response.read()
    except Exception:
        return None


def _extract_wav_bytes(raw: bytes) -> bytes | None:
    """Extract WAV bytes from direct payload or JSON body."""
    if not raw:
        return None
    if raw.startswith(b"RIFF"):
        return raw
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    audio_base64 = parsed.get("audio_base64")
    if not audio_base64:
        return None

    import base64

    try:
        wav_data = base64.b64decode(audio_base64)
    except Exception:
        return None
    return wav_data if wav_data.startswith(b"RIFF") else None


def _synthesize_wav_with_piper_http(text: str) -> bytes | None:
    """Generate WAV bytes from Piper HTTP server."""
    base_url = PIPER_HTTP_URL.rstrip("/")
    candidates = [
        (f"{base_url}/api/tts", json.dumps({"text": text, "voice": PIPER_VOICE}).encode("utf-8"), "application/json"),
        (f"{base_url}/synthesize", json.dumps({"text": text, "voice": PIPER_VOICE}).encode("utf-8"), "application/json"),
        (f"{base_url}/", json.dumps({"text": text, "voice": PIPER_VOICE}).encode("utf-8"), "application/json"),
        (f"{base_url}/api/tts", text.encode("utf-8"), "text/plain; charset=utf-8"),
    ]
    for url, payload, content_type in candidates:
        raw = _http_post(url, payload, content_type)
        wav_data = _extract_wav_bytes(raw or b"")
        if wav_data is not None:
            return wav_data
    return None


def _resolve_piper_command() -> str | None:
    """Resolve Piper executable path."""
    custom = PIPER_COMMAND.strip()
    if custom:
        if Path(custom).exists():
            return custom
        found = shutil.which(custom)
        if found:
            return found
    return shutil.which("piper")


def _resolve_model_path() -> str | None:
    """Resolve a local Piper voice model path."""
    explicit = PIPER_MODEL_PATH.strip()
    if explicit and Path(explicit).exists():
        return explicit

    if PIPER_VOICE.endswith(".onnx") and Path(PIPER_VOICE).exists():
        return PIPER_VOICE
    return None


def _synthesize_pcm_with_piper_cli(text: str) -> bytes | None:
    """Run Piper CLI and return raw int16 PCM bytes."""
    command = _resolve_piper_command()
    model_path = _resolve_model_path()
    if not command or not model_path:
        return None

    try:
        result = subprocess.run(
            [command, "--model", model_path, "--output-raw"],
            input=text.encode("utf-8"),
            check=False,
            text=False,
            capture_output=True,
        )
    except Exception as exc:
        print(f"[TTS] Piper CLI failed: {exc}")
        return None

    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="ignore").strip()
        print(f"[TTS] Piper CLI error: {err or 'unknown error'}")
        return None
    return result.stdout


def warm_tts() -> bool:
    """Check whether at least one Piper backend is reachable."""
    base_url = PIPER_HTTP_URL.rstrip("/")
    for health_url in (f"{base_url}/health", f"{base_url}/"):
        try:
            with request.urlopen(health_url, timeout=2):
                print("[TTS] Piper HTTP reachable.")
                return True
        except Exception:
            continue

    command = _resolve_piper_command()
    model_path = _resolve_model_path()
    if command and model_path:
        print(f"[TTS] Piper CLI ready ({Path(command).name}, model: {model_path}).")
        return True

    print("[TTS] Piper not ready. Configure Piper HTTP or set PIPER_MODEL_PATH.")
    return False


def speak_with_espeak(text: str) -> bool:
    """Optional fallback backend when Piper is unavailable."""
    if shutil.which("espeak") is None:
        return False
    result = subprocess.run(
        ["espeak", text],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def speak_text(text: str) -> bool:
    """Speak text with Piper and in-memory playback (no temp file writes)."""
    safe_text = _sanitize_text(text)
    if not safe_text:
        return False

    wav_bytes = _synthesize_wav_with_piper_http(safe_text)
    if wav_bytes is not None and _play_wav_bytes(wav_bytes):
        return True

    raw_pcm = _synthesize_pcm_with_piper_cli(safe_text)
    if raw_pcm is not None and _play_pcm_int16(raw_pcm, sample_rate=PIPER_SAMPLE_RATE):
        return True

    print("[TTS] Piper playback failed.")
    if ENABLE_TTS_FALLBACK_ESPEAK and speak_with_espeak(safe_text):
        print("[TTS] Using espeak fallback.")
        return True
    return False
