"""End-to-end Pi-side test for NOVA server reasoning with live YOLO detections."""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOVA_TESTING_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = NOVA_TESTING_DIR.parent

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(NOVA_TESTING_DIR))
sys.path.insert(0, str(NOVA_TESTING_DIR / "motor_voice_control"))

from nova_testing.config import CAMERA_INDEX, CV_CONFIDENCE_THRESHOLD, YOLO_MODEL_PATH  # noqa: E402
from nova_testing.nova_server.client.nova_server_client import (  # noqa: E402
    ask_nova_server,
    check_server_health,
)
from nova_testing.speech import speak_text  # noqa: E402
from motor_serial import MotorController  # noqa: E402
from config import BAUD_RATE, SERIAL_PORT, SERIAL_TIMEOUT_SECONDS  # noqa: E402

try:
    import cv2  # noqa: E402
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    from ultralytics import YOLO  # noqa: E402
except ImportError:  # pragma: no cover - environment dependent
    YOLO = None


DEFAULT_SERVER_URL = os.getenv("NOVA_SERVER_URL", "http://127.0.0.1:8080")
DEFAULT_EVENT = os.getenv("NOVA_REASON_EVENT", "good_morning")
DEFAULT_TRANSCRIPT = os.getenv("NOVA_REASON_TRANSCRIPT", "good morning nova")
DEFAULT_ROBOT_STATE = os.getenv("NOVA_REASON_ROBOT_STATE", "idle")
DISTANCE_QUERY_TIMEOUT_SECONDS = 1.0


def _position_from_center_x(center_x: float, frame_width: int) -> str:
    """Map a detection center point to left, center, or right."""
    if frame_width <= 0:
        return "unknown"

    left_boundary = frame_width / 3.0
    right_boundary = (frame_width * 2.0) / 3.0

    if center_x < left_boundary:
        return "left"
    if center_x > right_boundary:
        return "right"
    return "center"


def capture_live_detections() -> list[dict]:
    """Capture one live frame and convert YOLO detections into the server schema."""
    if cv2 is None:
        raise RuntimeError("opencv-python is not installed on the Pi.")
    if YOLO is None:
        raise RuntimeError("ultralytics is not installed on the Pi.")

    model = YOLO(YOLO_MODEL_PATH)
    capture = cv2.VideoCapture(CAMERA_INDEX)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("Could not open the Pi camera for live detection.")

    try:
        ok, frame = capture.read()
    finally:
        capture.release()

    if not ok or frame is None:
        raise RuntimeError("Could not capture a frame from the Pi camera.")

    frame_height, frame_width = frame.shape[:2]
    _ = frame_height  # retained for readability in case future logic needs it

    results = model(frame, verbose=False)
    detections: list[dict] = []

    for result in results:
        boxes = getattr(result, "boxes", None)
        names = getattr(result, "names", {})
        if boxes is None:
            continue

        for box in boxes:
            confidence = float(box.conf[0])
            if confidence < CV_CONFIDENCE_THRESHOLD:
                continue

            label_index = int(box.cls[0])
            label = str(names.get(label_index, f"class_{label_index}")).lower().strip()
            xyxy = box.xyxy[0].tolist()
            x1, _, x2, _ = xyxy
            center_x = (float(x1) + float(x2)) / 2.0
            position = _position_from_center_x(center_x, frame_width)

            detections.append(
                {
                    "label": label,
                    "confidence": round(confidence, 2),
                    "position": position,
                }
            )

    detections.sort(key=lambda item: (-float(item["confidence"]), item["label"]))
    return detections


def read_live_distance_inches() -> float | None:
    """Read one live ultrasonic distance value from the Arduino."""
    motor = MotorController(
        port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        timeout_seconds=SERIAL_TIMEOUT_SECONDS,
    )
    if not motor.connect():
        print("Could not connect to Arduino for ultrasonic distance.")
        return None

    try:
        response = motor.request_message(
            "DIST",
            expected_prefix="DIST",
            max_wait_seconds=DISTANCE_QUERY_TIMEOUT_SECONDS,
        )
    finally:
        motor.close()

    if not response:
        print("No ultrasonic distance response received.")
        return None

    parts = response.split(maxsplit=1)
    if len(parts) != 2:
        print(f"Unexpected ultrasonic response: {response}")
        return None

    value = parts[1].strip()
    if value.upper() == "ERR":
        print("Ultrasonic sensor returned DIST ERR.")
        return None

    try:
        return float(value)
    except ValueError:
        print(f"Invalid ultrasonic distance value: {response}")
        return None


def build_live_payload() -> dict:
    """Build a reasoning payload using live local detections from the Pi."""
    detections = capture_live_detections()
    distance_inches = read_live_distance_inches()
    return {
        "event": DEFAULT_EVENT,
        "transcript": DEFAULT_TRANSCRIPT,
        "detections": detections,
        "distance_inches": distance_inches,
        "robot_state": DEFAULT_ROBOT_STATE,
    }


def main() -> None:
    server_url = DEFAULT_SERVER_URL
    print(f"Checking NOVA server at {server_url}")
    healthy = check_server_health(server_url)
    print(f"healthy={healthy}")
    if not healthy:
        print("Server is not reachable from the Pi-side test path.")
        return

    print("Capturing live YOLO detections from the Pi...")
    payload = build_live_payload()
    print("Payload:")
    print(payload)

    print("Sending live reasoning payload...")
    response = ask_nova_server(server_url, payload)
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
