"""Use webcam detections to incrementally pan the camera servo toward a target."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import cv2
import serial

try:
    from ultralytics import YOLO
except ImportError as exc:  # pragma: no cover - environment dependent
    raise RuntimeError("ultralytics is required for servo_cv tracking.") from exc


DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD_RATE = 9600
DEFAULT_CAMERA_INDEX = 0
DEFAULT_MODEL_PATH = "yolo11n.pt"
DEFAULT_TARGET_LABEL = "person"
DEFAULT_CONFIDENCE = 0.45
DEFAULT_DEADZONE_RATIO = 0.2
DEFAULT_SERVO_CENTER_ANGLE = 90
DEFAULT_SERVO_MIN_ANGLE = 20
DEFAULT_SERVO_MAX_ANGLE = 160
DEFAULT_SMALL_STEP = 3
DEFAULT_LARGE_STEP = 7
DEFAULT_COMMAND_COOLDOWN = 0.2
DEFAULT_CONFIRM_FRAMES = 2
DEFAULT_LOST_TARGET_HOLD_SECONDS = 1.0
SERVO_BOOT_DELAY_SECONDS = 2.0


@dataclass
class Detection:
    label: str
    confidence: float
    center_x: float
    center_y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track a detected object and incrementally pan the Arduino-controlled camera servo.",
    )
    parser.add_argument("--port", default=DEFAULT_SERIAL_PORT, help="Arduino serial port.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE, help="Serial baud rate.")
    parser.add_argument("--camera-index", type=int, default=DEFAULT_CAMERA_INDEX, help="OpenCV camera index.")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="YOLO model path.")
    parser.add_argument("--target-label", default=DEFAULT_TARGET_LABEL, help="Object label to track.")
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE, help="Minimum detection confidence.")
    parser.add_argument(
        "--deadzone-ratio",
        type=float,
        default=DEFAULT_DEADZONE_RATIO,
        help="Centered zone width as a fraction of frame width.",
    )
    parser.add_argument("--servo-center-angle", type=int, default=DEFAULT_SERVO_CENTER_ANGLE, help="Center servo angle.")
    parser.add_argument("--servo-min-angle", type=int, default=DEFAULT_SERVO_MIN_ANGLE, help="Minimum safe servo angle.")
    parser.add_argument("--servo-max-angle", type=int, default=DEFAULT_SERVO_MAX_ANGLE, help="Maximum safe servo angle.")
    parser.add_argument("--small-step", type=int, default=DEFAULT_SMALL_STEP, help="Servo angle delta for moderate error.")
    parser.add_argument("--large-step", type=int, default=DEFAULT_LARGE_STEP, help="Servo angle delta for large error.")
    parser.add_argument(
        "--cooldown",
        type=float,
        default=DEFAULT_COMMAND_COOLDOWN,
        help="Minimum seconds between servo adjustments.",
    )
    parser.add_argument(
        "--confirm-frames",
        type=int,
        default=DEFAULT_CONFIRM_FRAMES,
        help="How many consecutive frames must agree before adjusting the servo.",
    )
    parser.add_argument(
        "--lost-target-hold-seconds",
        type=float,
        default=DEFAULT_LOST_TARGET_HOLD_SECONDS,
        help="How long to keep the current angle after the target disappears.",
    )
    parser.add_argument(
        "--show-window",
        action="store_true",
        help="Display the annotated webcam feed. Press q to quit.",
    )
    return parser


def open_serial(port: str, baud: int) -> serial.Serial:
    connection = serial.Serial(port, baud, timeout=1)
    time.sleep(SERVO_BOOT_DELAY_SECONDS)
    return connection


def send_servo_angle(connection: serial.Serial, angle: int) -> None:
    payload = f"SV{angle}\n".encode("utf-8")
    connection.write(payload)
    connection.flush()
    print(f"Sent servo angle: {angle}")


def find_best_detection(result, target_label: str, confidence_threshold: float) -> Detection | None:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return None

    best: Detection | None = None
    normalized_label = target_label.strip().lower()

    for box in boxes:
        confidence = float(box.conf[0])
        if confidence < confidence_threshold:
            continue

        label_index = int(box.cls[0])
        label = str(result.names.get(label_index, f"class_{label_index}")).strip().lower()
        if label != normalized_label:
            continue

        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0]]
        detection = Detection(
            label=label,
            confidence=confidence,
            center_x=(x1 + x2) / 2.0,
            center_y=(y1 + y2) / 2.0,
            width=max(x2 - x1, 0.0),
            height=max(y2 - y1, 0.0),
        )
        if best is None or detection.area > best.area:
            best = detection

    return best


def compute_servo_adjustment(frame_width: int, center_x: float, deadzone_ratio: float, small_step: int, large_step: int) -> int:
    midpoint = frame_width / 2.0
    offset = center_x - midpoint
    deadzone_half_width = (frame_width * deadzone_ratio) / 2.0
    large_error_threshold = frame_width * 0.25

    if abs(offset) <= deadzone_half_width:
        return 0

    step = large_step if abs(offset) >= large_error_threshold else small_step

    # Servo angle decreases when panning the camera to the right on the current mount.
    return -step if offset > 0 else step


def annotate_frame(frame, detection: Detection | None, servo_angle: int, deadzone_ratio: float):
    frame_height, frame_width = frame.shape[:2]
    midpoint = frame_width // 2
    deadzone_half_width = int((frame_width * deadzone_ratio) / 2.0)

    cv2.line(frame, (midpoint, 0), (midpoint, frame_height), (255, 255, 0), 1)
    cv2.line(frame, (midpoint - deadzone_half_width, 0), (midpoint - deadzone_half_width, frame_height), (0, 255, 255), 1)
    cv2.line(frame, (midpoint + deadzone_half_width, 0), (midpoint + deadzone_half_width, frame_height), (0, 255, 255), 1)

    status = f"Servo angle: {servo_angle}"
    cv2.putText(frame, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 220, 50), 2)

    if detection is None:
        cv2.putText(frame, "No target detected", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 255), 2)
        return frame

    half_width = detection.width / 2.0
    half_height = detection.height / 2.0
    x1 = int(detection.center_x - half_width)
    y1 = int(detection.center_y - half_height)
    x2 = int(detection.center_x + half_width)
    y2 = int(detection.center_y + half_height)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
    label_text = f"{detection.label} {detection.confidence:.2f}"
    cv2.putText(frame, label_text, (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
    return frame


def run(args: argparse.Namespace) -> int:
    model = YOLO(args.model)
    capture = cv2.VideoCapture(args.camera_index)
    if not capture.isOpened():
        print("Could not open camera.", file=sys.stderr)
        return 1

    try:
        connection = open_serial(args.port, args.baud)
    except serial.SerialException as exc:
        capture.release()
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1

    current_angle = max(min(args.servo_center_angle, args.servo_max_angle), args.servo_min_angle)
    last_command_time = 0.0
    candidate_adjustment = 0
    candidate_frames = 0
    last_detection_time = 0.0

    try:
        send_servo_angle(connection, current_angle)

        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("Failed to read frame.", file=sys.stderr)
                break

            results = model(frame, verbose=False)
            best_detection = None
            if results:
                best_detection = find_best_detection(
                    results[0],
                    target_label=args.target_label,
                    confidence_threshold=args.confidence,
                )

            if best_detection is not None:
                raw_adjustment = compute_servo_adjustment(
                    frame_width=frame.shape[1],
                    center_x=best_detection.center_x,
                    deadzone_ratio=args.deadzone_ratio,
                    small_step=args.small_step,
                    large_step=args.large_step,
                )
                last_detection_time = time.monotonic()
            else:
                raw_adjustment = 0

            now = time.monotonic()
            if best_detection is None and (now - last_detection_time) >= args.lost_target_hold_seconds:
                target_angle = max(min(args.servo_center_angle, args.servo_max_angle), args.servo_min_angle)
                raw_adjustment = target_angle - current_angle

            if raw_adjustment == 0:
                candidate_adjustment = 0
                candidate_frames = 0
                desired_adjustment = 0
            else:
                direction = 1 if raw_adjustment > 0 else -1
                if direction == candidate_adjustment:
                    candidate_frames += 1
                else:
                    candidate_adjustment = direction
                    candidate_frames = 1

                if candidate_frames >= max(args.confirm_frames, 1):
                    desired_adjustment = raw_adjustment
                else:
                    desired_adjustment = 0

            if desired_adjustment != 0 and (now - last_command_time) >= args.cooldown:
                new_angle = current_angle + desired_adjustment
                new_angle = max(min(new_angle, args.servo_max_angle), args.servo_min_angle)
                if new_angle != current_angle:
                    send_servo_angle(connection, new_angle)
                    current_angle = new_angle
                    last_command_time = now
                candidate_adjustment = 0
                candidate_frames = 0

            if args.show_window:
                annotated = annotate_frame(frame.copy(), best_detection, current_angle, args.deadzone_ratio)
                cv2.imshow("Servo CV Tracker", annotated)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

            if args.frame_interval > 0:
                time.sleep(args.frame_interval)
    except KeyboardInterrupt:
        print("\nStopping servo CV tracker.")
    finally:
        try:
            center_angle = max(min(args.servo_center_angle, args.servo_max_angle), args.servo_min_angle)
            send_servo_angle(connection, center_angle)
        except Exception:
            pass
        connection.close()
        capture.release()
        cv2.destroyAllWindows()

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
