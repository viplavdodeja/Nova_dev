"""Runtime configuration for NOVA multimodal testing."""

from __future__ import annotations

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "nova"
OLLAMA_KEEP_ALIVE = "15m"
OLLAMA_TIMEOUT_SECONDS = 30

PIPER_HTTP_URL = "http://localhost:5000"
PIPER_VOICE = "en_US-lessac-medium"
PIPER_HTTP_TIMEOUT_SECONDS = 20
PIPER_COMMAND = "piper"
PIPER_MODEL_PATH = "/home/novarobot/capstone_project/nova_testing_backup/en_US-lessac-medium.onnx"
PIPER_SAMPLE_RATE = 22050
ENABLE_TTS_FALLBACK_ESPEAK = True

VOSK_MODEL_PATH = "vosk-model-small-en-us-0.15"
MIC_DEVICE_INDEX = None
STT_SAMPLE_RATE = 16000
STT_BLOCK_SIZE = 8000
STT_LISTEN_TIMEOUT_SECONDS = 8.0

CAMERA_INDEX = 0
CV_CONFIDENCE_THRESHOLD = 0.5
YOLO_MODEL_PATH = "yolo11n.pt"
FRAME_SAMPLE_COUNT = 3
FRAME_SAMPLE_INTERVAL_SECONDS = 1.0
PIPELINE_LOOP_DELAY_SECONDS = 1.5
MAX_PENDING_TTS_RESPONSES = 1

SPEECH_ENABLED = True
CV_ENABLED = True
STT_ENABLED = False
