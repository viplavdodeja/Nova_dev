"""Full NOVA demo script with voice control, servo tracking, and server-backed greeting replies."""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOVA_TESTING_DIR = Path(__file__).resolve().parents[1]
NOVA_DEMO_DIR = Path(__file__).resolve().parent
MOTOR_DIR = NOVA_TESTING_DIR / "motor_voice_control"

sys.path.insert(0, str(REPO_ROOT))
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
    COMMAND_LISTEN_TIMEOUT_SECONDS,
    GREETING_LOOK_PAUSE_SECONDS,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
    SPIN_360_DEFAULT_MS,
    WAKE_PHRASE,
    WAKE_REQUIRED_HITS,
)
from motor_serial import MotorController  # noqa: E402
from motor_voice_streaming import ContinuousVoskListener  # noqa: E402
from servo_tracking import ServoPersonTracker  # noqa: E402

from nova_testing.nova_server.client.nova_server_client import (  # noqa: E402
    ask_nova_server,
    check_server_health,
)


LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"
SERVER_URL = os.getenv("NOVA_SERVER_URL", "http://127.0.0.1:8080")
SERVER_REASON_TIMEOUT_LABEL = "server-demo"


def _load_root_speech_module():
    """Load nova_testing/speech.py without colliding with motor config imports."""
    module_path = NOVA_TESTING_DIR / "speech.py"
    spec = importlib.util.spec_from_file_location("nova_testing_root_speech_server_demo", module_path)
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


def start_speech(text: str) -> threading.Thread | None:
    """Start local TTS output in the background and return the worker thread."""
    if not text:
        return None

    def _speak_worker() -> None:
        if not speak_text(text):
            print("[ServerDemo] Speech output failed.")

    worker = threading.Thread(target=_speak_worker, daemon=True, name="server-demo-tts")
    worker.start()
    return worker


def execute_greeting_sequence(send_payload) -> None:
    """Run the local Pi/Arduino greeting movement sequence."""
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


def read_distance_inches(motor: MotorController, serial_lock: threading.Lock) -> float | None:
    """Read one ultrasonic value from the Arduino over the existing serial connection."""
    with serial_lock:
        response = motor.request_message("DIST", expected_prefix="DIST", max_wait_seconds=1.0)

    if not response:
        print("[ServerDemo] No ultrasonic distance response received.")
        return None

    parts = response.split(maxsplit=1)
    if len(parts) != 2:
        print(f"[ServerDemo] Unexpected ultrasonic response: {response}")
        return None

    value = parts[1].strip()
    if value.upper() == "ERR":
        print("[ServerDemo] Ultrasonic sensor returned DIST ERR.")
        return None

    try:
        return float(value)
    except ValueError:
        print(f"[ServerDemo] Invalid ultrasonic distance value: {response}")
        return None


def build_server_payload(
    transcript: str,
    greeting: str,
    tracker: ServoPersonTracker,
    motor: MotorController,
    serial_lock: threading.Lock,
) -> dict:
    """Build the server reasoning payload from live local Pi state."""
    detections: list[dict] = []
    snapshot = tracker.get_last_detection()
    if snapshot is not None:
        position = "center"
        if snapshot.center_x < snapshot.frame_width / 3.0:
            position = "left"
        elif snapshot.center_x > (snapshot.frame_width * 2.0) / 3.0:
            position = "right"

        detections.append(
            {
                "label": snapshot.label,
                "confidence": round(snapshot.confidence, 2),
                "position": position,
            }
        )

    event = greeting.replace(" ", "_")
    distance_inches = read_distance_inches(motor, serial_lock)
    return {
        "event": event,
        "transcript": transcript,
        "detections": detections,
        "distance_inches": distance_inches,
        "robot_state": "idle",
    }


def run() -> None:
    """Run the full server-backed NOVA greeting demo."""
    os.chdir(MOTOR_DIR)
    listener = ContinuousVoskListener()
    ok, message = listener.validate_environment()
    if not ok:
        print(message)
        return
    if not listener.start():
        return

    motor = MotorController(
        port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        timeout_seconds=SERIAL_TIMEOUT_SECONDS,
    )
    if not motor.connect():
        listener.stop()
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

    yolo_model_path = NOVA_TESTING_DIR.parent / "yolo11n.pt"
    tracker = ServoPersonTracker(
        send_payload=send_payload,
        model_path=str(yolo_model_path) if yolo_model_path.exists() else "yolo11n.pt",
    )

    warm_tts()
    send_led(LED_IDLE)
    tracker.start()

    server_healthy = check_server_health(SERVER_URL)
    print("Server demo started")
    print(f"Server URL: {SERVER_URL}")
    print(f"Server healthy: {server_healthy}")
    print("Idle behavior: wake phrase listening + servo person tracking")
    print("Greeting behavior: local motion + server reasoning + local speech")
    print("Press Ctrl+C to stop\n")

    wake_hits = 0
    previous_passive_text = ""

    try:
        while True:
            current_passive_text = normalize_text(listener.listen_for_passive_trigger())
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
                print(f"Wake word detected: {WAKE_PHRASE} ({wake_hits}/{WAKE_REQUIRED_HITS})")
            else:
                wake_hits = 0

            if wake_hits >= WAKE_REQUIRED_HITS:
                wake_hits = 0
                previous_passive_text = ""
                send_led(LED_COMMAND)
                tracker.pause()
                try:
                    print("Listening for command...")
                    command_text = normalize_text(listener.listen_for_command(COMMAND_LISTEN_TIMEOUT_SECONDS))
                    if command_text:
                        print(f"Heard (command): {command_text}")

                    greeting = parse_greeting_command(command_text)
                    if greeting is not None:
                        print(f"Greeting recognized: {greeting}")
                        payload = build_server_payload(command_text, greeting, tracker, motor, serial_lock)
                        print("Server payload:")
                        print(payload)
                        response = ask_nova_server(SERVER_URL, payload)
                        print("Server response:")
                        print(response)
                        reply = str(response.get("reply", "")).strip()
                        speech_thread = start_speech(reply)
                        execute_greeting_sequence(send_payload)
                        if speech_thread is not None:
                            speech_thread.join()
                        send_led(LED_IDLE)
                        previous_passive_text = ""
                        continue

                    parsed = parse_motor_command(command_text)
                    if parsed is None:
                        print("No valid command recognized")
                        send_led(LED_IDLE)
                        previous_passive_text = ""
                        continue

                    phrase, serial_command, duration_ms = parsed
                    print(f"Command recognized: {phrase}")
                    payload = serial_command if duration_ms is None else f"{serial_command}{duration_ms}"
                    print(f"Sending motion payload: {payload}")
                    send_payload(payload)
                    if duration_ms is None:
                        send_led(LED_IDLE)
                    previous_passive_text = ""
                    continue
                finally:
                    tracker.resume()

            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down server demo")
    finally:
        tracker.stop()
        send_led(LED_IDLE)
        motor.close()
        listener.stop()


if __name__ == "__main__":
    run()
