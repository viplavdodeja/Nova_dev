"""Shared background person-tracking servo loop for Nova demo scripts."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

try:
    import cv2
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - environment dependent
    YOLO = None

DEFAULT_CAMERA_INDEX = 0
DEFAULT_MODEL_PATH = "yolo11n.pt"
DEFAULT_TARGET_LABEL = "person"
DEFAULT_CONFIDENCE = 0.45
DEFAULT_DEADZONE_RATIO = 0.2
DEFAULT_SERVO_CENTER_ANGLE = 90
DEFAULT_SERVO_MIN_ANGLE = 20
DEFAULT_SERVO_MAX_ANGLE = 160
DEFAULT_SMALL_STEP = 7
DEFAULT_LARGE_STEP = 15
DEFAULT_COMMAND_COOLDOWN = 0.2
DEFAULT_CONFIRM_FRAMES = 2
DEFAULT_LOST_TARGET_HOLD_SECONDS = 1.0
DEFAULT_FRAME_INTERVAL = 0.1


@dataclass(slots=True)
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


@dataclass(slots=True)
class DetectionSnapshot:
    label: str
    confidence: float
    center_x: float
    center_y: float
    width: float
    height: float
    frame_width: int
    frame_height: int


class ServoPersonTracker:
    """Run track_and_pan-style person tracking against a shared serial sender."""

    def __init__(
        self,
        send_payload: Callable[[str], bool],
        camera_index: int = DEFAULT_CAMERA_INDEX,
        model_path: str = DEFAULT_MODEL_PATH,
        target_label: str = DEFAULT_TARGET_LABEL,
        confidence: float = DEFAULT_CONFIDENCE,
        deadzone_ratio: float = DEFAULT_DEADZONE_RATIO,
        servo_center_angle: int = DEFAULT_SERVO_CENTER_ANGLE,
        servo_min_angle: int = DEFAULT_SERVO_MIN_ANGLE,
        servo_max_angle: int = DEFAULT_SERVO_MAX_ANGLE,
        small_step: int = DEFAULT_SMALL_STEP,
        large_step: int = DEFAULT_LARGE_STEP,
        cooldown: float = DEFAULT_COMMAND_COOLDOWN,
        confirm_frames: int = DEFAULT_CONFIRM_FRAMES,
        lost_target_hold_seconds: float = DEFAULT_LOST_TARGET_HOLD_SECONDS,
        frame_interval: float = DEFAULT_FRAME_INTERVAL,
    ) -> None:
        self._send_payload = send_payload
        self._camera_index = camera_index
        self._model_path = model_path
        self._target_label = target_label
        self._confidence = confidence
        self._deadzone_ratio = deadzone_ratio
        self._servo_center_angle = servo_center_angle
        self._servo_min_angle = servo_min_angle
        self._servo_max_angle = servo_max_angle
        self._small_step = small_step
        self._large_step = large_step
        self._cooldown = cooldown
        self._confirm_frames = confirm_frames
        self._lost_target_hold_seconds = lost_target_hold_seconds
        self._frame_interval = frame_interval
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_angle = self._clamp_angle(servo_center_angle)
        self._state_lock = threading.Lock()
        self._last_detection: DetectionSnapshot | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="servo-person-tracker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def get_last_detection(self) -> DetectionSnapshot | None:
        """Return the most recent tracked detection snapshot, if any."""
        with self._state_lock:
            return self._last_detection

    def _run(self) -> None:
        if cv2 is None or YOLO is None:
            print("[ServoTracker] opencv-python and ultralytics are required; tracking disabled.")
            return

        try:
            model = YOLO(self._model_path)
        except Exception as exc:
            print(f"[ServoTracker] Could not load YOLO model: {exc}")
            return

        capture = cv2.VideoCapture(self._camera_index)
        if not capture.isOpened():
            capture.release()
            print("[ServoTracker] Could not open camera; tracking disabled.")
            return

        last_command_time = 0.0
        candidate_adjustment = 0
        candidate_frames = 0
        last_detection_time = 0.0

        try:
            self._send_angle(self._current_angle)
            while not self._stop_event.is_set():
                if self._pause_event.is_set():
                    time.sleep(self._frame_interval)
                    continue

                ok, frame = capture.read()
                if not ok or frame is None:
                    time.sleep(self._frame_interval)
                    continue

                results = model(frame, verbose=False)
                best_detection = None
                if results:
                    best_detection = self._find_best_detection(results[0])

                with self._state_lock:
                    if best_detection is None:
                        self._last_detection = None
                    else:
                        self._last_detection = DetectionSnapshot(
                            label=best_detection.label,
                            confidence=best_detection.confidence,
                            center_x=best_detection.center_x,
                            center_y=best_detection.center_y,
                            width=best_detection.width,
                            height=best_detection.height,
                            frame_width=frame.shape[1],
                            frame_height=frame.shape[0],
                        )

                if best_detection is not None:
                    raw_adjustment = self._compute_servo_adjustment(frame.shape[1], best_detection.center_x)
                    last_detection_time = time.monotonic()
                else:
                    raw_adjustment = 0

                now = time.monotonic()
                if best_detection is None and (now - last_detection_time) >= self._lost_target_hold_seconds:
                    raw_adjustment = self._clamp_angle(self._servo_center_angle) - self._current_angle

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
                    desired_adjustment = raw_adjustment if candidate_frames >= max(self._confirm_frames, 1) else 0

                if desired_adjustment != 0 and (now - last_command_time) >= self._cooldown:
                    new_angle = self._clamp_angle(self._current_angle + desired_adjustment)
                    if new_angle != self._current_angle:
                        self._send_angle(new_angle)
                        self._current_angle = new_angle
                        last_command_time = now
                    candidate_adjustment = 0
                    candidate_frames = 0

                time.sleep(self._frame_interval)
        finally:
            try:
                self._send_angle(self._clamp_angle(self._servo_center_angle))
            except Exception:
                pass
            capture.release()

    def _find_best_detection(self, result) -> Detection | None:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return None

        best: Detection | None = None
        normalized_label = self._target_label.strip().lower()

        for box in boxes:
            confidence = float(box.conf[0])
            if confidence < self._confidence:
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

    def _compute_servo_adjustment(self, frame_width: int, center_x: float) -> int:
        midpoint = frame_width / 2.0
        offset = center_x - midpoint
        deadzone_half_width = (frame_width * self._deadzone_ratio) / 2.0
        large_error_threshold = frame_width * 0.25

        if abs(offset) <= deadzone_half_width:
            return 0

        step = self._large_step if abs(offset) >= large_error_threshold else self._small_step
        return -step if offset > 0 else step

    def _send_angle(self, angle: int) -> None:
        self._send_payload(f"SV{angle}")

    def _clamp_angle(self, angle: int) -> int:
        return max(min(angle, self._servo_max_angle), self._servo_min_angle)
