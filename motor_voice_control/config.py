"""Configuration for Raspberry Pi motor voice control."""

from __future__ import annotations

from pathlib import Path

# Serial link to Arduino.
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600
SERIAL_TIMEOUT_SECONDS = 1.0

# Wake phrase and clip durations.
WAKE_PHRASE = "hey nova"
PASSIVE_CLIP_DURATION_SECONDS = 2.0
COMMAND_CLIP_DURATION_SECONDS = 4.0

# Require N wake detections before entering command mode.
# Set to 2 for fewer false wakes in noisy spaces.
WAKE_REQUIRED_HITS = 1

# arecord microphone settings.
ARECORD_DEVICE = "default"  # Example: "hw:1,0" if needed
ARECORD_SAMPLE_RATE = 16000
ARECORD_CHANNELS = 1
ARECORD_FORMAT = "S16_LE"

# whisper.cpp paths (update these on the Pi).
WHISPER_EXECUTABLE_PATH = "/home/novarobot/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL_PATH = "/home/novarobot/whisper.cpp/models/ggml-tiny.en.bin"
WHISPER_LANGUAGE = "en"
WHISPER_THREADS = 4

# Optional passive-mode VAD (recommended if your whisper build supports it).
ENABLE_PASSIVE_VAD = False
WHISPER_VAD_MODEL_PATH = ""
WHISPER_VAD_THRESHOLD = 0.5

# Optional command grammar for constrained decoding.
ENABLE_COMMAND_GRAMMAR = True
COMMAND_GRAMMAR_PATH = Path("command_grammar.gbnf")

# Temporary audio directory used for WAV chunks.
TEMP_AUDIO_DIR = Path("audio_files")
