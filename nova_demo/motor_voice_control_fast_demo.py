"""Motor voice demo with tracking, greeting animation, and whisper.cpp STT."""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import importlib.util
from pathlib import Path

NOVA_TESTING_DIR = Path(__file__).resolve().parents[1]
NOVA_DEMO_DIR = Path(__file__).resolve().parent
MOTOR_DIR = NOVA_TESTING_DIR / "motor_voice_control"

sys.path.insert(0, str(NOVA_DEMO_DIR))
sys.path.insert(0, str(MOTOR_DIR))

from command_parser import (  # noqa: E402
    contains_emergency_stop,
    contains_wake_phrase,
    normalize_text,
    parse_greeting_command,
    parse_motor_command,
)
from config import (  # noqa: E402
    BAUD_RATE,
    GREETING_LOOK_PAUSE_SECONDS,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
    SPIN_360_DEFAULT_MS,
    WAKE_REQUIRED_HITS,
)
from motor_serial import MotorController  # noqa: E402
from servo_tracking import ServoPersonTracker  # noqa: E402
from speech_listener_whisper_cpp import WhisperCppListener  # noqa: E402


def _load_root_speech_module():
    """Load nova_testing/speech.py without shadowing motor_voice_control/config.py."""
    module_path = NOVA_TESTING_DIR / "speech.py"
    spec = importlib.util.spec_from_file_location("nova_testing_root_speech", module_path)
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

LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"

PRESET_GREETING_RESPONSES = {
    "good morning": "Good morning",
    "hello": "Hello I'm NOVA",
}


class TTSWorker:
    """Persistent one-item TTS worker to avoid per-command Python startup."""

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="fast-demo-tts")

    def start(self) -> None:
        warm_tts()
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def say(self, text: str) -> None:
        if not text:
            return
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if not speak_text(text):
                print("[TTS] Speech output failed.")


def preset_response_for(command_text: str) -> str | None:
    normalized = normalize_text(command_text)
    for phrase, response in PRESET_GREETING_RESPONSES.items():
        if phrase in normalized:
            return response
    return None


def execute_greeting_sequence(send_payload) -> None:
    """Run the greeting motion sequence using existing serial commands."""
    sequence = (
        ("LOOK_LEFT", GREETING_LOOK_PAUSE_SECONDS),
        ("LOOK_RIGHT", GREETING_LOOK_PAUSE_SECONDS),
        ("LOOK_CENTER", GREETING_LOOK_PAUSE_SECONDS),
        (f"SR{SPIN_360_DEFAULT_MS}", 0.0),
    )

    for payload, pause_seconds in sequence:
        print(f"Sending greeting payload: {payload}")
        send_payload(payload)
        if pause_seconds > 0:
            time.sleep(pause_seconds)


def run() -> None:
    """Run the fast demo loop."""
    os.chdir(MOTOR_DIR)
    listener = WhisperCppListener()
    ok, message = listener.validate_environment()
    if not ok:
        print(message)
        return

    motor = MotorController(
        port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        timeout_seconds=SERIAL_TIMEOUT_SECONDS,
    )
    if not motor.connect():
        return

    serial_lock = threading.Lock()

    def send_payload(payload: str) -> bool:
        with serial_lock:
            return motor.send_message(payload)

    def send_led(token: str) -> bool:
        with serial_lock:
            return motor.set_led_state(token)

    def send_command(command: str) -> bool:
        with serial_lock:
            return motor.send_command(command)

    tts_worker = TTSWorker()
    tts_worker.start()

    yolo_model_path = NOVA_TESTING_DIR.parent / "yolo11n.pt"
    tracker = ServoPersonTracker(
        send_payload=send_payload,
        model_path=str(yolo_model_path) if yolo_model_path.exists() else "yolo11n.pt",
    )

    send_led(LED_IDLE)
    tracker.start()

    print("Fast Nova motor voice demo started")
    print("Uses arecord + whisper.cpp temp clips for wake/commands and persistent TTS.")
    print("Passive listening mode active")
    print("Press Ctrl+C to stop\n")

    wake_hits = 0
    previous_passive_text = ""

    try:
        while True:
            current_passive_text = normalize_text(
                listener.listen_once(listener.passive_duration_seconds(), command_mode=False)
            )
            if current_passive_text:
                print(f"Heard (passive): {current_passive_text}")

            combined_passive_text = normalize_text(
                f"{previous_passive_text} {current_passive_text}".strip()
            )

            if contains_emergency_stop(combined_passive_text):
                print("Emergency stop detected")
                send_command("X")
                wake_hits = 0
                previous_passive_text = ""
                continue

            if contains_wake_phrase(combined_passive_text):
                wake_hits += 1
                print(f"Wake word detected: nova ({wake_hits}/{WAKE_REQUIRED_HITS})")
            else:
                wake_hits = 0

            if wake_hits >= WAKE_REQUIRED_HITS:
                wake_hits = 0
                previous_passive_text = ""
                send_led(LED_COMMAND)

                tracker.pause()
                try:
                    print("Listening for command...")
                    command_text = normalize_text(
                        listener.listen_once(listener.command_duration_seconds(), command_mode=True)
                    )
                finally:
                    tracker.resume()

                if command_text:
                    print(f"Heard (command): {command_text}")

                greeting = parse_greeting_command(command_text)
                if greeting is not None:
                    print(f"Greeting recognized: {greeting}")
                    response = preset_response_for(command_text)
                    if response is not None:
                        print(f"Nova preset response: {response}")
                        tts_worker.say(response)
                    tracker.pause()
                    try:
                        execute_greeting_sequence(send_payload)
                    finally:
                        tracker.resume()
                    send_led(LED_IDLE)
                    continue

                parsed = parse_motor_command(command_text)
                if parsed is None:
                    print("No valid command recognized")
                    send_led(LED_IDLE)
                    continue

                phrase, serial_command, duration_ms = parsed
                print(f"Command recognized: {phrase}")
                payload = serial_command if duration_ms is None else f"{serial_command}{duration_ms}"
                print(f"Sending motion payload: {payload}")
                send_payload(payload)
                if duration_ms is None:
                    send_led(LED_IDLE)
                continue

            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down fast Nova motor voice demo")
    finally:
        tracker.stop()
        tts_worker.stop()
        send_led(LED_IDLE)
        motor.close()


if __name__ == "__main__":
    run()
