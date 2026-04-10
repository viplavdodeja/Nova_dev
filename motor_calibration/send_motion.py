"""Send raw timed motion commands to the Arduino for calibration."""

from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports


DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 9600
DEFAULT_TIMEOUT = 1.0
DEFAULT_POST_SEND_DELAY = 0.2

COMMAND_MAP = {
    "forward": "F",
    "backward": "B",
    "left-turn": "L",
    "right-turn": "R",
    "spin-left": "SL",
    "spin-right": "SR",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send timed motion commands over serial for robot calibration.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=sorted(COMMAND_MAP),
        help="Motion to send.",
    )
    parser.add_argument(
        "duration_ms",
        nargs="?",
        type=int,
        help="Duration in milliseconds for the motion.",
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Serial device path. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Serial baud rate. Default: {DEFAULT_BAUD}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Serial read timeout in seconds. Default: {DEFAULT_TIMEOUT}",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List detected serial ports and exit.",
    )
    parser.add_argument(
        "--raw",
        help="Send a raw serial line instead of using action + duration.",
    )
    parser.add_argument(
        "--read-response",
        action="store_true",
        help="Read and print Arduino output after sending.",
    )
    parser.add_argument(
        "--read-seconds",
        type=float,
        default=2.0,
        help="How long to read responses when --read-response is enabled.",
    )
    return parser


def list_available_ports() -> int:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return 1

    print("Detected serial ports:")
    for port in ports:
        description = port.description or "Unknown device"
        print(f"  {port.device}  {description}")
    return 0


def build_payload(action: str | None, duration_ms: int | None, raw: str | None) -> str:
    if raw:
        return raw.strip()

    if action is None or duration_ms is None:
        raise ValueError("Provide action and duration_ms, or use --raw.")

    if duration_ms <= 0:
        raise ValueError("duration_ms must be a positive integer.")

    return f"{COMMAND_MAP[action]}{duration_ms}"


def read_responses(connection: serial.Serial, read_seconds: float) -> None:
    deadline = time.monotonic() + max(read_seconds, 0.0)
    while time.monotonic() < deadline:
        line = connection.readline()
        if not line:
            continue
        decoded = line.decode("utf-8", errors="replace").strip()
        if decoded:
            print(f"Arduino: {decoded}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_ports:
        return list_available_ports()

    try:
        payload = build_payload(args.action, args.duration_ms, args.raw)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        with serial.Serial(args.port, args.baud, timeout=args.timeout) as connection:
            # Give boards that auto-reset on open a moment to settle.
            time.sleep(2.0)

            wire_payload = (payload + "\n").encode("utf-8")
            connection.write(wire_payload)
            connection.flush()
            print(f"Sent: {payload}")

            time.sleep(DEFAULT_POST_SEND_DELAY)
            if args.read_response:
                read_responses(connection, args.read_seconds)
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
