"""Main loop for wake-phrase motor voice control on Raspberry Pi."""

from __future__ import annotations

from command_parser import (
    contains_emergency_stop,
    contains_wake_phrase,
    normalize_text,
    parse_motor_command,
)
from config import (
    BAUD_RATE,
    COMMAND_CLIP_DURATION_SECONDS,
    PASSIVE_CLIP_DURATION_SECONDS,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
)
from motor_serial import MotorController
from speech_listener import WhisperCppListener


def run() -> None:
    """Run passive listening and command mode loops."""
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

    print("Voice motor control started")
    print("Passive listening mode active")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            passive_text = normalize_text(listener.listen_once(PASSIVE_CLIP_DURATION_SECONDS))
            if passive_text:
                print(f"Heard (passive): {passive_text}")

            # Emergency stop has highest priority in passive mode.
            if contains_emergency_stop(passive_text):
                print("Emergency stop detected")
                motor.send_command("S")
                continue

            if contains_wake_phrase(passive_text):
                print("Wake phrase detected: hey nova")
                print("Listening for command...")
                command_text = normalize_text(listener.listen_once(COMMAND_CLIP_DURATION_SECONDS))
                if command_text:
                    print(f"Heard (command): {command_text}")

                parsed = parse_motor_command(command_text)
                if parsed is None:
                    print("No valid command recognized")
                    continue

                phrase, letter = parsed
                print(f"Command recognized: {phrase}")
                motor.send_command(letter)
    except KeyboardInterrupt:
        print("\nShutting down voice motor control")
    finally:
        motor.close()


if __name__ == "__main__":
    run()
