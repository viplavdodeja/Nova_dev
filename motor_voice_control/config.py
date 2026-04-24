"""Configuration for Raspberry Pi motor voice control."""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default

# Serial link to Arduino.
# Override with NOVA_SERIAL_PORT if needed. Use "auto" to probe common Linux ports.
SERIAL_PORT = os.getenv("NOVA_SERIAL_PORT", "auto")
BAUD_RATE = 9600
SERIAL_TIMEOUT_SECONDS = 1.0

# Wake phrase and rolling command timings.
WAKE_PHRASE = "nova"
PASSIVE_LISTEN_TIMEOUT_SECONDS = 2.0
COMMAND_LISTEN_TIMEOUT_SECONDS = 4.0
GREETING_COMMANDS = (
    "hello",
    "good morning",
    "good afternoon",
    "good evening",
)
GREETING_LOOK_PAUSE_SECONDS = 1.0

# Require N wake detections before entering command mode.
# Set to 2 for fewer false wakes in noisy spaces.
WAKE_REQUIRED_HITS = 1

# Legacy Python-whisper settings kept for optional experiments.
MIC_DEVICE_INDEX = _env_int("NOVA_MIC_DEVICE_INDEX", None)
STT_SAMPLE_RATE = 16000
STT_BLOCK_SIZE = 8000
STT_DEBUG = os.getenv("NOVA_STT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

# Whisper STT settings. Used by the motor voice control runtime for wake/command recognition.
WHISPER_MODEL_NAME = os.getenv("NOVA_WHISPER_MODEL", "base.en")
WHISPER_LANGUAGE = "en"
WHISPER_TASK = "transcribe"
WHISPER_WAKE_RECORD_SECONDS = 2.0
WHISPER_SILENCE_RMS_THRESHOLD = 0.01
WHISPER_INITIAL_PROMPT = (
    "Robot voice commands: nova, stop, forward, backward, turn left, "
    "turn right, spin, look left, look right, look forward, hello, "
    "good morning, good afternoon, good evening."
)

# whisper.cpp temporary-audio STT settings used by fast demo.
ARECORD_DEVICE = os.getenv("NOVA_ARECORD_DEVICE", "default")
ARECORD_SAMPLE_RATE = 16000
ARECORD_CHANNELS = 1
ARECORD_FORMAT = "S16_LE"
WHISPER_EXECUTABLE_PATH = os.getenv(
    "NOVA_WHISPER_CPP_EXECUTABLE",
    "/home/novarobot/whisper.cpp/build/bin/whisper-cli",
)
WHISPER_MODEL_PATH = os.getenv(
    "NOVA_WHISPER_CPP_MODEL",
    "/home/novarobot/whisper.cpp/models/ggml-small.en.bin",
)
WHISPER_THREADS = _env_int("NOVA_WHISPER_CPP_THREADS", 4) or 4
ENABLE_PASSIVE_VAD = os.getenv("NOVA_WHISPER_CPP_VAD", "").strip().lower() in {"1", "true", "yes", "on"}
WHISPER_VAD_MODEL_PATH = os.getenv("NOVA_WHISPER_CPP_VAD_MODEL", "")
WHISPER_VAD_THRESHOLD = 0.5
ENABLE_COMMAND_GRAMMAR = True
COMMAND_GRAMMAR_PATH = Path("command_grammar.gbnf")
TEMP_AUDIO_DIR = Path("audio_files")
WHISPER_CPP_PASSIVE_MODE_SECONDS = 2.0
WHISPER_CPP_COMMAND_MODE_SECONDS = 4.0

# Distance calibration tables.
# Each tuple is: (distance_in_inches, duration_ms)
# Replace these example values with your measured best-fit durations.
FORWARD_DISTANCE_CALIBRATION_IN = [
    (5.0, 200),
    (10.0, 390),
    (20.0, 780),
]

BACKWARD_DISTANCE_CALIBRATION_IN = [
    (5.0, 200),
    (10.0, 390),
    (20.0, 780),
]

# Calibrated motion timings in milliseconds.
FORWARD_DEFAULT_MS = 1000
BACKWARD_DEFAULT_MS = 1000
TURN_LEFT_DEFAULT_MS = 280
TURN_RIGHT_DEFAULT_MS = 280
U_TURN_DEFAULT_MS = 545
SPIN_360_DEFAULT_MS = 1085
