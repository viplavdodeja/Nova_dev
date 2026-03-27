"""Configuration for Whisper mic testing."""

from __future__ import annotations

WHISPER_MODEL_NAME = "base.en"
WHISPER_LANGUAGE = "en"
WHISPER_TASK = "transcribe"

MIC_DEVICE_INDEX = None
TARGET_SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 4.0

# Ignore very quiet clips to reduce pointless transcriptions.
SILENCE_RMS_THRESHOLD = 0.01
