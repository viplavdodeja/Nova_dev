"""Wake-phrase motor voice control with preset spoken greeting responses."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
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
    COMMAND_LISTEN_TIMEOUT_SECONDS,
    GREETING_LOOK_PAUSE_SECONDS,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
    SPIN_360_DEFAULT_MS,
    WAKE_REQUIRED_HITS,
)
from motor_serial import MotorController  # noqa: E402
from servo_tracking import ServoPersonTracker  # noqa: E402
from speech_listener import ContinuousVoskListener  # noqa: E402

LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"

PRESET_GREETING_RESPONSES = {
    "good morning": "Good morning",
    "hello": "Hello I'm NOVA",
}


def speak_async(text: str) -> None:
    """Speak through the existing nova_testing speech.py path in an isolated process."""
    if not text:
        return

    code = (
        "import sys\n"
        "from speech import speak_text\n"
        "raise SystemExit(0 if speak_text(sys.argv[1]) else 1)\n"
    )
    thread = threading.Thread(
        target=subprocess.run,
        args=([sys.executable, "-c", code, text],),
        kwargs={"cwd": str(NOVA_TESTING_DIR), "check": False},
        daemon=True,
        name="preset-greeting-tts",
    )
    thread.start()


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
    """Run continuous passive listening with preset greeting speech."""
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

    tracker = ServoPersonTracker(send_payload=send_payload)
    send_led(LED_IDLE)
    tracker.start()

    print("Voice motor control with preset greeting speech started")
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
                print(f"Wake phrase detected: hey nova ({wake_hits}/{WAKE_REQUIRED_HITS})")
            else:
                wake_hits = 0

            if wake_hits >= WAKE_REQUIRED_HITS:
                wake_hits = 0
                previous_passive_text = ""
                send_led(LED_COMMAND)
                print("Listening for command...")
                command_text = normalize_text(listener.listen_for_command(COMMAND_LISTEN_TIMEOUT_SECONDS))
                if command_text:
                    print(f"Heard (command): {command_text}")

                greeting = parse_greeting_command(command_text)
                if greeting is not None:
                    print(f"Greeting recognized: {greeting}")
                    response = preset_response_for(command_text)
                    if response is not None:
                        print(f"Nova preset response: {response}")
                        speak_async(response)
                    tracker.pause()
                    try:
                        execute_greeting_sequence(send_payload)
                    finally:
                        tracker.resume()
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

            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down voice motor control")
    finally:
        tracker.stop()
        send_led(LED_IDLE)
        motor.close()
        listener.stop()


if __name__ == "__main__":
    run()
