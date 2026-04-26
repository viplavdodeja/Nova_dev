"""Manual terminal-to-Arduino serial console for Nova demo fallback."""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOVA_TESTING_DIR = Path(__file__).resolve().parents[1]
MOTOR_DIR = NOVA_TESTING_DIR / "motor_voice_control"

sys.path.insert(0, str(MOTOR_DIR))

from config import BAUD_RATE, SERIAL_PORT, SERIAL_TIMEOUT_SECONDS  # noqa: E402
from motor_serial import MotorController  # noqa: E402


HELP_TEXT = """Commands:
  F, B, L, R, X
  F1000, B1000, L300, R300
  SL1000, SR1000
  LOOK_LEFT, LOOK_RIGHT, LOOK_CENTER
  SV30, SV90, SV150
  DIST
  LED_READY, LED_LISTEN, LED_MOVE, LED_ERROR
  help
  quit
"""


def main() -> None:
    os.chdir(MOTOR_DIR)

    motor = MotorController(
        port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        timeout_seconds=SERIAL_TIMEOUT_SECONDS,
    )
    if not motor.connect():
        return

    print("Nova terminal serial console")
    print("Type Arduino serial commands and press Enter.")
    print("Type `help` for examples or `quit` to exit.\n")

    try:
        while True:
            try:
                raw = input("nova> ")
            except EOFError:
                break

            command = raw.strip()
            if not command:
                continue

            lowered = command.lower()
            if lowered in {"quit", "exit"}:
                break
            if lowered in {"help", "?"}:
                print(HELP_TEXT)
                continue

            if command.strip().upper() == "DIST":
                response = motor.request_message("DIST", expected_prefix="DIST", max_wait_seconds=1.0)
                print(f"arduino> {response if response else '<no response>'}")
                continue

            motor.send_message(command)
    except KeyboardInterrupt:
        print("\nStopping terminal serial console")
    finally:
        motor.close()


if __name__ == "__main__":
    main()
