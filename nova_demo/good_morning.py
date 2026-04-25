"""One-shot good morning intro script for Nova demo."""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

NOVA_TESTING_DIR = Path(__file__).resolve().parents[1]
NOVA_DEMO_DIR = Path(__file__).resolve().parent
MOTOR_DIR = NOVA_TESTING_DIR / "motor_voice_control"

sys.path.insert(0, str(MOTOR_DIR))

from config import (  # noqa: E402
    BAUD_RATE,
    GREETING_LOOK_PAUSE_SECONDS,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
    SPIN_360_DEFAULT_MS,
)
from motor_serial import MotorController  # noqa: E402


INTRO_TEXT = "Good morning, I am Nova. Nice to meet you."
LED_IDLE = "LED_READY"
SPEECH_PREROLL_SECONDS = 1.5


def _load_root_speech_module():
    """Load nova_testing/speech.py without shadowing motor config imports."""
    module_path = NOVA_TESTING_DIR / "speech.py"
    spec = importlib.util.spec_from_file_location("nova_testing_root_speech_good_morning", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load speech module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    previous_config = sys.modules.pop("config", None)
    sys.path.insert(0, str(NOVA_TESTING_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(NOVA_TESTING_DIR))
        except ValueError:
            pass
        if previous_config is not None:
            sys.modules["config"] = previous_config
        else:
            sys.modules.pop("config", None)
    return module


_ROOT_SPEECH = _load_root_speech_module()
speak_text = _ROOT_SPEECH.speak_text
warm_tts = _ROOT_SPEECH.warm_tts
_speech_sd = getattr(_ROOT_SPEECH, "sd", None)
_speech_np = getattr(_ROOT_SPEECH, "np", None)
_speech_sample_rate = getattr(_ROOT_SPEECH, "PIPER_SAMPLE_RATE", 22050)


def _play_silence(seconds: float) -> None:
    """Play silent audio to wake the speaker path before speech starts."""
    if seconds <= 0 or _speech_sd is None or _speech_np is None:
        return
    frames = max(1, int(_speech_sample_rate * seconds))
    silence = _speech_np.zeros(frames, dtype=_speech_np.int16)
    try:
        _speech_sd.play(silence, samplerate=_speech_sample_rate, blocking=True)
    except Exception as exc:
        print(f"[TTS] Silence preroll failed: {exc}")


def speak_blocking(text: str) -> None:
    """Speak with silence preroll and wait for completion."""
    if not text:
        return
    _play_silence(SPEECH_PREROLL_SECONDS)
    if not speak_text(text):
        print("[TTS] Speech output failed.")


def execute_greeting_sequence(motor: MotorController) -> None:
    """Run the intro motion sequence."""
    sequence = (
        ("LOOK_LEFT", GREETING_LOOK_PAUSE_SECONDS),
        ("LOOK_RIGHT", GREETING_LOOK_PAUSE_SECONDS),
        ("LOOK_CENTER", GREETING_LOOK_PAUSE_SECONDS),
        (f"SR{SPIN_360_DEFAULT_MS}", 0.0),
    )

    for payload, pause_seconds in sequence:
        print(f"Sending greeting payload: {payload}")
        motor.send_message(payload)
        if pause_seconds > 0:
            time.sleep(pause_seconds)


def main() -> None:
    os.chdir(MOTOR_DIR)
    motor = MotorController(
        port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        timeout_seconds=SERIAL_TIMEOUT_SECONDS,
    )
    if not motor.connect():
        return

    try:
        warm_tts()
        motor.set_led_state(LED_IDLE)
        execute_greeting_sequence(motor)
        speak_blocking(INTRO_TEXT)
    finally:
        motor.set_led_state(LED_IDLE)
        motor.close()


if __name__ == "__main__":
    main()
