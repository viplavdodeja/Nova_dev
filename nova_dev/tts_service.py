"""Text-to-speech service wrapper for Nova responses."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path
from queue import Queue
from urllib import request

import numpy as np

from config import RuntimeConfig
from events import Event, EventType

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - environment dependent
    sd = None


class TTSService:
    """Coordinator-facing text-to-speech wrapper."""

    def __init__(self, event_queue: Queue[Event], config: RuntimeConfig) -> None:
        self._event_queue = event_queue
        self._config = config

    def warm(self) -> bool:
        base_url = self._config.piper_http_url.rstrip("/")
        for health_url in (f"{base_url}/health", f"{base_url}/"):
            try:
                with request.urlopen(health_url, timeout=2):
                    print("[TTS] Piper HTTP reachable.")
                    return True
            except Exception:
                continue

        command = self._resolve_piper_command()
        model_path = self._resolve_model_path()
        if command and model_path:
            print(f"[TTS] Piper CLI ready ({Path(command).name}, model: {model_path}).")
            return True

        print("[TTS] Piper not ready. Falling back if possible.")
        return False

    def speak(self, text: str) -> None:
        safe_text = self._sanitize_text(text)
        if not safe_text:
            return
        self._event_queue.put(Event(type=EventType.TTS_STARTED, source="tts", payload={"text": safe_text}))

        success = False
        wav_bytes = self._synthesize_wav_with_piper_http(safe_text)
        if wav_bytes is not None:
            success = self._play_wav_bytes(wav_bytes)

        if not success:
            raw_pcm = self._synthesize_pcm_with_piper_cli(safe_text)
            if raw_pcm is not None:
                success = self._play_pcm_int16(raw_pcm, sample_rate=self._config.piper_sample_rate)

        if not success and self._config.enable_tts_fallback_espeak:
            success = self._speak_with_espeak(safe_text)

        if not success:
            print("[TTS] Playback failed.")

        self._event_queue.put(Event(type=EventType.TTS_FINISHED, source="tts", payload={"text": safe_text, "success": success}))

    @staticmethod
    def _sanitize_text(text: str) -> str:
        safe = re.sub(r"[\x00-\x1F\x7F]", " ", text)
        safe = re.sub(r"\s+", " ", safe).strip()
        return safe[:500]

    def _play_pcm_int16(self, raw_bytes: bytes, sample_rate: int) -> bool:
        if not raw_bytes or sd is None:
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

    def _play_wav_bytes(self, wav_bytes: bytes) -> bool:
        if not wav_bytes or not wav_bytes.startswith(b"RIFF") or sd is None:
            return False
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
                channels = reader.getnchannels()
                sample_width = reader.getsampwidth()
                sample_rate = reader.getframerate()
                frames = reader.readframes(reader.getnframes())
            if sample_width != 2:
                return False
            audio = np.frombuffer(frames, dtype=np.int16)
            if channels > 1:
                audio = audio.reshape(-1, channels)
            sd.play(audio, samplerate=sample_rate, blocking=True)
            return True
        except Exception as exc:
            print(f"[TTS] WAV playback failed: {exc}")
            return False

    def _http_post(self, url: str, payload: bytes, content_type: str) -> bytes | None:
        req = request.Request(url, data=payload, method="POST", headers={"Content-Type": content_type})
        try:
            with request.urlopen(req, timeout=self._config.piper_http_timeout_seconds) as response:
                return response.read()
        except Exception:
            return None

    def _extract_wav_bytes(self, raw: bytes) -> bytes | None:
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

    def _synthesize_wav_with_piper_http(self, text: str) -> bytes | None:
        base_url = self._config.piper_http_url.rstrip("/")
        candidates = [
            (f"{base_url}/api/tts", json.dumps({"text": text, "voice": self._config.piper_voice}).encode("utf-8"), "application/json"),
            (f"{base_url}/synthesize", json.dumps({"text": text, "voice": self._config.piper_voice}).encode("utf-8"), "application/json"),
            (f"{base_url}/", json.dumps({"text": text, "voice": self._config.piper_voice}).encode("utf-8"), "application/json"),
        ]
        for url, payload, content_type in candidates:
            raw = self._http_post(url, payload, content_type)
            wav_data = self._extract_wav_bytes(raw or b"")
            if wav_data is not None:
                return wav_data
        return None

    def _resolve_piper_command(self) -> str | None:
        custom = self._config.piper_command.strip()
        if custom:
            if Path(custom).exists():
                return custom
            found = shutil.which(custom)
            if found:
                return found
        return shutil.which("piper")

    def _resolve_model_path(self) -> str | None:
        explicit = self._config.piper_model_path.strip()
        if explicit and Path(explicit).exists():
            return explicit
        if self._config.piper_voice.endswith(".onnx") and Path(self._config.piper_voice).exists():
            return self._config.piper_voice
        return None

    def _synthesize_pcm_with_piper_cli(self, text: str) -> bytes | None:
        command = self._resolve_piper_command()
        model_path = self._resolve_model_path()
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
            return None
        return result.stdout

    @staticmethod
    def _speak_with_espeak(text: str) -> bool:
        if shutil.which("espeak") is None:
            return False
        result = subprocess.run(["espeak", text], check=False, capture_output=True, text=True)
        return result.returncode == 0
