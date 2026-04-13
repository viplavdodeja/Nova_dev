"""Configuration for Raspberry Pi motor voice control."""

from __future__ import annotations

# Serial link to Arduino.
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600
SERIAL_TIMEOUT_SECONDS = 1.0

# Wake phrase and rolling command timings.
WAKE_PHRASE = "hey nova"
PASSIVE_LISTEN_TIMEOUT_SECONDS = 2.0
COMMAND_LISTEN_TIMEOUT_SECONDS = 4.0

# Require N wake detections before entering command mode.
# Set to 2 for fewer false wakes in noisy spaces.
WAKE_REQUIRED_HITS = 1

# Continuous Vosk STT settings.
VOSK_MODEL_PATH = "vosk-model-small-en-us-0.15"
MIC_DEVICE_INDEX = None
STT_SAMPLE_RATE = 16000
STT_BLOCK_SIZE = 8000

# Calibrated linear travel speed.
ROBOT_SPEED_CM_PER_SEC = 62.3

# Calibrated motion timings in milliseconds.
FORWARD_DEFAULT_MS = 1000
BACKWARD_DEFAULT_MS = 1000
TURN_LEFT_DEFAULT_MS = 250
TURN_RIGHT_DEFAULT_MS = 250
U_TURN_DEFAULT_MS = 515
SPIN_360_DEFAULT_MS = 1030
