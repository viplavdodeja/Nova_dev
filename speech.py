"""Piper HTTP-first speech output for NOVA on Raspberry Pi/Linux."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from urllib import request

from config import (
    ENABLE_TTS_FALLBACK_ESPEAK,
    OPTIONAL_LEADING_SILENCE_MS,
    PIPER_HTTP_TIMEOUT_SECONDS,
    PIPER_HTTP_URL,
    PIPER_VOICE,
)


def _sanitize_text(text: str) -> str:
    """Return speech text cleaned for stable TTS behavior."""
    safe = re.sub(r"[\x00-\x1F\x7F]", " ", text)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:500]


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
    """Extract WAV bytes from server response."""
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


def _prepend_silence_ms(wav_path: Path, silence_ms: int) -> bool:
    """Optionally prepend silence to WAV to avoid clipped first syllable."""
    if silence_ms <= 0:
        return True
    try:
        with wave.open(str(wav_path), "rb") as reader:
            params = reader.getparams()
            frames = reader.readframes(reader.getnframes())
        channels = params.nchannels
        sample_width = params.sampwidth
        frame_rate = params.framerate
        silence_frames = int(frame_rate * (silence_ms / 1000.0))
        silence_chunk = b"\x00" * silence_frames * channels * sample_width
        with wave.open(str(wav_path), "wb") as writer:
            writer.setparams(params)
            writer.writeframes(silence_chunk + frames)
        return True
    except Exception:
        return False


def _play_wav(wav_path: Path) -> bool:
    """Play WAV via aplay."""
    if shutil.which("aplay") is None:
        print("[TTS] aplay is missing.")
        return False
    try:
        result = subprocess.run(
            ["aplay", str(wav_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        print(f"[TTS] Playback failed: {exc}")
        return False
    if result.returncode != 0:
        err = (result.stderr or "").strip()
        print(f"[TTS] aplay failed: {err or 'unknown error'}.")
        return False
    return True


def warm_tts() -> bool:
    """Check Piper HTTP reachability."""
    base_url = PIPER_HTTP_URL.rstrip("/")
    health_urls = [f"{base_url}/health", f"{base_url}/"]
    for url in health_urls:
        try:
            with request.urlopen(url, timeout=2):
                print("[TTS] Piper HTTP reachable.")
                return True
        except Exception:
            continue
    print(f"[TTS] Piper HTTP not reachable at {PIPER_HTTP_URL}.")
    return False


def speak_with_espeak(text: str) -> bool:
    """Optional fallback backend when Piper HTTP is unavailable."""
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
    """Speak text with Piper HTTP first; fallback to espeak if enabled."""
    safe_text = _sanitize_text(text)
    if not safe_text:
        return False

    wav_bytes = _synthesize_wav_with_piper_http(safe_text)
    if wav_bytes is not None:
        wav_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                wav_path = Path(tmp_file.name)
                tmp_file.write(wav_bytes)
            _prepend_silence_ms(wav_path, OPTIONAL_LEADING_SILENCE_MS)
            if _play_wav(wav_path):
                return True
        except Exception as exc:
            print(f"[TTS] Piper HTTP playback path failed: {exc}")
        finally:
            if wav_path is not None:
                try:
                    wav_path.unlink(missing_ok=True)
                except Exception:
                    pass

    print("[TTS] Piper HTTP failed.")
    if ENABLE_TTS_FALLBACK_ESPEAK and speak_with_espeak(safe_text):
        print("[TTS] Using espeak fallback.")
        return True
    return False
