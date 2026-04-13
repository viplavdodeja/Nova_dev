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
    COMMAND_LISTEN_TIMEOUT_SECONDS,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
    WAKE_REQUIRED_HITS,
)
from motor_serial import MotorController
from speech_listener import ContinuousVoskListener

LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"


def run() -> None:
    """Run continuous passive listening with rolling command capture."""
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
    motor.set_led_state(LED_IDLE)

    print("Voice motor control started")
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

            # Emergency stop has highest priority in passive mode.
            if contains_emergency_stop(combined_passive_text):
                print("Emergency stop detected")
                motor.send_command("X")
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
                motor.set_led_state(LED_COMMAND)
                print("Listening for command...")
                command_text = normalize_text(listener.listen_for_command(COMMAND_LISTEN_TIMEOUT_SECONDS))
                if command_text:
                    print(f"Heard (command): {command_text}")

                parsed = parse_motor_command(command_text)
                if parsed is None:
                    print("No valid command recognized")
                    motor.set_led_state(LED_IDLE)
                    previous_passive_text = ""
                    continue

                phrase, serial_command, duration_ms = parsed
                print(f"Command recognized: {phrase}")
                if duration_ms is None:
                    payload = serial_command
                else:
                    payload = f"{serial_command}{duration_ms}"
                print(f"Sending motion payload: {payload}")
                motor.send_message(payload)
                if duration_ms is None:
                    motor.set_led_state(LED_IDLE)
                previous_passive_text = ""
                continue

            # Keep one-step memory only; clear if no speech this chunk.
            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down voice motor control")
    finally:
        motor.set_led_state(LED_IDLE)
        motor.close()
        listener.stop()


if __name__ == "__main__":
    run()
