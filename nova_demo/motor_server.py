"""Motor voice demo with local motion/tracking and server-side LLM text decisions."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib import error, request

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


LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"

SERVER_URL = os.getenv("NOVA_SERVER_URL", "http://127.0.0.1:8000/nova/respond")
SERVER_TIMEOUT_SECONDS = float(os.getenv("NOVA_SERVER_TIMEOUT_SECONDS", "20"))
SCENE_FRAME_COUNT = int(os.getenv("NOVA_SERVER_SCENE_FRAME_COUNT", "1"))
SCENE_INTERVAL_SECONDS = float(os.getenv("NOVA_SERVER_SCENE_INTERVAL_SECONDS", "0.0"))
SERVER_FALLBACK_RESPONSE = "Hello, I'm NOVA."


def _load_root_module(module_name: str, file_name: str):
    """Load a nova_testing module without shadowing motor config imports."""
    module_path = NOVA_TESTING_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")
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


_ROOT_SPEECH = _load_root_module("nova_testing_root_speech_for_server", "speech.py")
_ROOT_VISION = _load_root_module("nova_testing_root_vision_for_server", "vision.py")

speak_text = _ROOT_SPEECH.speak_text
warm_tts = _ROOT_SPEECH.warm_tts
get_scene_text_burst = _ROOT_VISION.get_scene_text_burst


def request_server_response(command_text: str, scene_text: str) -> str:
    """Send command and scene summary to server and return response text."""
    payload = {
        "command_text": command_text,
        "scene_text": scene_text,
        "mode": "greeting",
    }
    req = request.Request(
        SERVER_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=SERVER_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8")
    except error.URLError as exc:
        print(f"[Server] Could not reach {SERVER_URL}: {exc}")
        return SERVER_FALLBACK_RESPONSE
    except TimeoutError:
        print(f"[Server] Request timed out after {SERVER_TIMEOUT_SECONDS} seconds.")
        return SERVER_FALLBACK_RESPONSE
    except Exception as exc:
        print(f"[Server] Request failed: {exc}")
        return SERVER_FALLBACK_RESPONSE

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        print("[Server] Response was not valid JSON.")
        return SERVER_FALLBACK_RESPONSE

    response_text = str(
        body.get("speak_text")
        or body.get("response")
        or body.get("text")
        or ""
    ).strip()
    return response_text or SERVER_FALLBACK_RESPONSE


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
    """Run local wake/command/motion and remote server-side LLM speech decisions."""
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

    print("Motor server demo started")
    print("Local: wake word, STT commands, motor safety, servo tracking")
    print(f"Remote speech logic server: {SERVER_URL}")
    print(f"Wake phrase: {WAKE_PHRASE}")
    print("Passive listening mode active")
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
                        scene_text, _per_frame, aggregated = get_scene_text_burst(
                            frame_count=SCENE_FRAME_COUNT,
                            interval_seconds=SCENE_INTERVAL_SECONDS,
                        )
                        if aggregated:
                            print(f"[Scene] {aggregated}")
                        print(f"[Scene Text] {scene_text}")

                        execute_greeting_sequence(send_payload)
                        response = request_server_response(command_text, scene_text)
                        print(f"[Server Response] {response}")
                        speak_text(response)
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
                finally:
                    tracker.resume()

            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down motor server demo")
    finally:
        tracker.stop()
        send_led(LED_IDLE)
        motor.close()
        listener.stop()


if __name__ == "__main__":
    run()
