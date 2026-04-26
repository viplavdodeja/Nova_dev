"""End-to-end Pi-side test for NOVA server reasoning and local speech."""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOVA_TESTING_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = NOVA_TESTING_DIR.parent
NOVA_SERVER_DIR = NOVA_TESTING_DIR / "nova_server"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(NOVA_TESTING_DIR))

from nova_testing.nova_server.client.nova_server_client import (  # noqa: E402
    ask_nova_server,
    check_server_health,
)
from speech import speak_text  # noqa: E402


DEFAULT_SERVER_URL = os.getenv("NOVA_SERVER_URL", "http://127.0.0.1:8080")

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
    server_url = DEFAULT_SERVER_URL
    print(f"Checking NOVA server at {server_url}")
    healthy = check_server_health(server_url)
    print(f"healthy={healthy}")
    if not healthy:
        print("Server is not reachable from the Pi-side test path.")
        return

    print("Sending sample reasoning payload...")
    response = ask_nova_server(server_url, SAMPLE_PAYLOAD)
    print("Server response:")
    print(response)

    reply = str(response.get("reply", "")).strip()
    if not reply:
        print("No reply text returned.")
        return

    print(f"Speaking: {reply}")
    ok = speak_text(reply)
    print(f"speech_ok={ok}")


if __name__ == "__main__":
    main()
