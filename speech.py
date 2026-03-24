"""Piper-first text-to-speech helpers for NOVA testing on Linux/Pi."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PIPER_PYTHON_BIN = "python3"
PIPER_VOICE_MODEL = "en_US-lessac-medium"
ENABLE_ESPEAK_FALLBACK = True


def _sanitize_text(text: str) -> str:
    """Return text safe for command arguments and speech engines."""
    safe_text = re.sub(r"[\x00-\x1F\x7F]", " ", text)
    safe_text = re.sub(r"\s+", " ", safe_text).strip()
    return safe_text[:500]


def speak_with_piper(text: str) -> bool:
    """Speak text with Piper and return True on success."""
    if shutil.which("aplay") is None:
        print("[TTS] aplay is not installed.")
        return False

    temp_wav_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            temp_wav_path = Path(tmp_file.name)

        render = subprocess.run(
            [
                PIPER_PYTHON_BIN,
                "-m",
                "piper",
                "-m",
                PIPER_VOICE_MODEL,
                "-f",
                str(temp_wav_path),
                "--",
                text,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if render.returncode != 0:
            stderr = (render.stderr or "").strip()
            print(f"[TTS] Piper generation failed: {stderr or 'unknown error'}.")
            return False

        play = subprocess.run(
            ["aplay", str(temp_wav_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if play.returncode != 0:
            stderr = (play.stderr or "").strip()
            print(f"[TTS] aplay failed: {stderr or 'unknown error'}.")
            return False
        return True
    except FileNotFoundError:
        print("[TTS] Piper is not installed or python3 is unavailable.")
        return False
    except Exception as exc:
        print(f"[TTS] Piper speech failed: {exc}")
        return False
    finally:
        if temp_wav_path is not None:
            try:
                temp_wav_path.unlink(missing_ok=True)
            except Exception:
                pass


def speak_with_espeak(text: str) -> bool:
    """Fallback speech method using espeak."""
    if shutil.which("espeak") is None:
        print("[TTS] espeak fallback is not installed.")
        return False
    completed = subprocess.run(
        ["espeak", text],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        print(f"[TTS] espeak fallback failed: {stderr or 'unknown error'}.")
        return False
    return True


def speak_text(text: str) -> bool:
    """Speak text using Piper first, with optional espeak fallback."""
    safe_text = _sanitize_text(text)
    if not safe_text:
        print("[TTS] Empty text, skipping speech.")
        return False

    try:
        if speak_with_piper(safe_text):
            return True
        if ENABLE_ESPEAK_FALLBACK and speak_with_espeak(safe_text):
            return True
        print("[TTS] No speech backend succeeded.")
        return False
    except Exception as exc:
        print(f"[TTS] Unexpected speech error: {exc}")
        return False
