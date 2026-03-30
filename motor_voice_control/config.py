"""Configuration for Raspberry Pi motor voice control."""

from __future__ import annotations

from pathlib import Path

# Serial link to Arduino.
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600
SERIAL_TIMEOUT_SECONDS = 1.0

# Wake phrase and clip durations.
WAKE_PHRASE = "hey nova"
PASSIVE_CLIP_DURATION_SECONDS = 3.0
COMMAND_CLIP_DURATION_SECONDS = 3.0

# arecord microphone settings.
ARECORD_DEVICE = "default"  # Example: "hw:1,0" if needed
ARECORD_SAMPLE_RATE = 16000
ARECORD_CHANNELS = 1
ARECORD_FORMAT = "S16_LE"

# whisper.cpp paths (update these on the Pi).
WHISPER_EXECUTABLE_PATH = "/home/novarobot/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL_PATH = "/home/novarobot/whisper.cpp/models/ggml-tiny.en.bin"
WHISPER_LANGUAGE = "en"

# Temporary audio directory used for WAV chunks.
TEMP_AUDIO_DIR = Path("audio_files")
