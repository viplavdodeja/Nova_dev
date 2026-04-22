"""Configuration for the Nova integrated runtime."""

from __future__ import annotations

import os

from dataclasses import dataclass, field


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class RuntimeConfig:
    """Coordinator-level runtime settings."""

    serial_port: str = os.getenv("NOVA_SERIAL_PORT", "auto")
    baud_rate: int = 9600
    serial_timeout_seconds: float = 1.0

    wake_phrase: str = "nova"
    passive_listen_timeout_seconds: float = 2.0
    command_listen_timeout_seconds: float = 4.0
    vosk_model_path: str = os.getenv("NOVA_VOSK_MODEL_PATH", "vosk-model-small-en-us-0.15")
    mic_device_index: int | None = None
    stt_sample_rate: int = 16000
    stt_block_size: int = 8000

    camera_index: int = 0
    cv_enabled: bool = True
    cv_confidence_threshold: float = 0.5
    yolo_model_path: str = "yolo11n.pt"
    frame_sample_count: int = 3
    frame_sample_interval_seconds: float = 0.25
    observe_loop_delay_seconds: float = 0.25
    cv_cycle_interval_seconds: float = 2.0
    target_label: str = "person"
    autonomous_cv_enabled: bool = _env_flag("NOVA_AUTONOMOUS_CV_ENABLED", False)
    autonomous_cv_cooldown_seconds: float = 6.0

    speech_enabled: bool = True
    tts_enabled: bool = True
    piper_http_url: str = "http://localhost:5000"
    piper_voice: str = "en_US-lessac-medium"
    piper_http_timeout_seconds: int = 20
    piper_command: str = "piper"
    piper_model_path: str = "/home/novarobot/capstone_project/nova_testing_backup/en_US-lessac-medium.onnx"
    piper_sample_rate: int = 22050
    enable_tts_fallback_espeak: bool = True

    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "nova"
    ollama_keep_alive: str = "15m"
    ollama_timeout_seconds: int = 30

    motion_payloads: dict[str, str] = field(
        default_factory=lambda: {
            "forward": "F1000",
            "backward": "B1000",
            "turn_left": "L250",
            "turn_right": "R250",
            "u_turn_left": "L450",
            "u_turn_right": "R450",
            "spin_left": "SL900",
            "spin_right": "SR900",
            "stop": "X",
        }
    )
    servo_angles: dict[str, int] = field(
        default_factory=lambda: {
            "look_left": 150,
            "look_center": 90,
            "look_right": 30,
        }
    )
    queue_poll_timeout_seconds: float = 0.1
