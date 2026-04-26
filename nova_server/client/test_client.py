"""Small command-line test client for the NOVA server."""

from __future__ import annotations

import argparse
import json

from .nova_server_client import ask_nova_server, check_server_health


SAMPLE_PAYLOAD = {
    "event": "good_morning",
    "transcript": "good morning nova",
    "detections": [
        {
            "label": "person",
            "confidence": 0.94,
            "position": "center",
        }
    ],
    "distance_inches": 28,
    "robot_state": "idle",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the NOVA server reasoning endpoint.")
    parser.add_argument(
        "--server-url",
        default="http://127.0.0.1:8080",
        help="Base URL for the NOVA server.",
    )
    args = parser.parse_args()

    print(f"Checking server health at {args.server_url} ...")
    healthy = check_server_health(args.server_url)
    print(f"healthy={healthy}")

    print("\nSending sample payload:")
    print(json.dumps(SAMPLE_PAYLOAD, indent=2))

    response = ask_nova_server(args.server_url, SAMPLE_PAYLOAD)
    print("\nServer response:")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
