"""Speech listener based on arecord + whisper.cpp CLI."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from config import (
    ARECORD_CHANNELS,
    ARECORD_DEVICE,
    ARECORD_FORMAT,
    ARECORD_SAMPLE_RATE,
    COMMAND_GRAMMAR_PATH,
    ENABLE_COMMAND_GRAMMAR,
    ENABLE_PASSIVE_VAD,
    TEMP_AUDIO_DIR,
    WHISPER_CPP_COMMAND_MODE_SECONDS,
    WHISPER_CPP_PASSIVE_MODE_SECONDS,
    WHISPER_EXECUTABLE_PATH,
    WHISPER_LANGUAGE,
    WHISPER_MODEL_PATH,
    WHISPER_THREADS,
    WHISPER_VAD_MODEL_PATH,
    WHISPER_VAD_THRESHOLD,
)


class WhisperCppListener:
    """Temporary-file STT adapter using arecord and whisper.cpp."""

    def __init__(self) -> None:
        self.audio_dir = TEMP_AUDIO_DIR
        self.whisper_executable = Path(WHISPER_EXECUTABLE_PATH)
        self.whisper_model = Path(WHISPER_MODEL_PATH)

    def validate_environment(self) -> tuple[bool, str]:
        """Validate required binaries and model path."""
        if shutil.which("arecord") is None:
            return False, "Missing microphone tool: arecord not found"
        if not self.whisper_executable.exists():
            return False, f"Missing whisper.cpp executable: {self.whisper_executable}"
        if not self.whisper_model.exists():
            return False, f"Missing whisper model path: {self.whisper_model}"
        return True, ""

    def passive_duration_seconds(self) -> float:
        return WHISPER_CPP_PASSIVE_MODE_SECONDS

    def command_duration_seconds(self) -> float:
        return WHISPER_CPP_COMMAND_MODE_SECONDS

    def record_audio(self, output_path: Path, duration_seconds: float) -> bool:
        """Record one WAV chunk with arecord."""
        duration_whole_seconds = max(1, int(math.ceil(float(duration_seconds))))
        cmd = [
            "arecord",
            "-D",
            ARECORD_DEVICE,
            "-f",
            ARECORD_FORMAT,
            "-r",
            str(ARECORD_SAMPLE_RATE),
            "-c",
            str(ARECORD_CHANNELS),
            "-d",
            str(duration_whole_seconds),
            "-q",
            str(output_path),
        ]
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            print("Missing microphone recording tool: arecord")
            return False
        except Exception as exc:
            print(f"arecord execution error: {exc}")
            return False

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            print(f"arecord failed: {err or 'unknown error'}")
            return False
        return output_path.exists()

    def _build_whisper_command(
        self,
        audio_path: Path,
        command_mode: bool,
        use_grammar: bool = True,
    ) -> list[str]:
        """Build whisper.cpp command with mode-specific options."""
        cmd = [
            str(self.whisper_executable),
            "-m",
            str(self.whisper_model),
            "-f",
            str(audio_path),
            "-l",
            WHISPER_LANGUAGE,
            "-t",
            str(WHISPER_THREADS),
            "--no-timestamps",
            "--print-progress",
            "false",
            "--no-prints",
        ]

        if not command_mode and ENABLE_PASSIVE_VAD:
            cmd.append("--vad")
            if WHISPER_VAD_MODEL_PATH:
                vad_path = Path(WHISPER_VAD_MODEL_PATH)
                if vad_path.exists():
                    cmd.extend(["--vad-model", str(vad_path)])
            cmd.extend(["--vad-threshold", str(WHISPER_VAD_THRESHOLD)])

        if command_mode and use_grammar and ENABLE_COMMAND_GRAMMAR and COMMAND_GRAMMAR_PATH.exists():
            cmd.extend(["--grammar", str(COMMAND_GRAMMAR_PATH)])

        return cmd

    def transcribe_audio(self, audio_path: Path, command_mode: bool = False) -> str:
        """Transcribe a WAV file via whisper.cpp CLI."""
        cmd = self._build_whisper_command(audio_path=audio_path, command_mode=command_mode)

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except Exception as exc:
            print(f"whisper.cpp execution failure: {exc}")
            return ""

        if result.returncode != 0 and command_mode and ENABLE_COMMAND_GRAMMAR:
            fallback_cmd = self._build_whisper_command(
                audio_path=audio_path,
                command_mode=True,
                use_grammar=False,
            )
            try:
                result = subprocess.run(fallback_cmd, check=False, capture_output=True, text=True)
            except Exception:
                pass

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            print(f"whisper.cpp failed: {err or 'unknown error'}")
            return ""

        transcript = self._extract_transcript(result.stdout)
        return transcript.lower().strip()

    def listen_once(self, duration_seconds: float, command_mode: bool = False) -> str:
        """Record and transcribe one short clip, then return transcript."""
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"clip_{uuid4().hex}.wav"
        wav_path = self.audio_dir / file_name

        if not self.record_audio(wav_path, duration_seconds):
            return ""

        return self.transcribe_audio(wav_path, command_mode=command_mode)

    @staticmethod
    def _extract_transcript(stdout_text: str) -> str:
        """Extract transcript from whisper.cpp output."""
        lines = [line.strip() for line in (stdout_text or "").splitlines() if line.strip()]
        if not lines:
            return ""

        candidates: list[str] = []
        for line in lines:
            cleaned = re.sub(r"^\[[^\]]+\]\s*", "", line)
            cleaned = re.sub(r"^\(\d+%\)\s*", "", cleaned)
            cleaned = cleaned.strip()
            if not cleaned:
                continue
            if cleaned.lower().startswith("system_info"):
                continue
            if cleaned.lower().startswith("main:"):
                continue
            candidates.append(cleaned)

        return " ".join(candidates).strip()
