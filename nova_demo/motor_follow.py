"""Wake-phrase motor voice control with preset spoken greeting responses."""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from dataclasses import dataclass
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
    WAKE_PHRASE,
    WAKE_REQUIRED_HITS,
)
from motor_serial import MotorController  # noqa: E402
from motor_voice_streaming import ContinuousVoskListener  # noqa: E402

try:
    import cv2
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - environment dependent
    YOLO = None

LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"
SPEECH_PREROLL_SECONDS = 1.5
FOLLOW_TURN_BURST_MS = 220
FOLLOW_FORWARD_BURST_MS = 280
FOLLOW_SETTLE_SECONDS = 0.35
FOLLOW_CENTER_DEADZONE_RATIO = 0.12
FOLLOW_STOP_DISTANCE_INCHES = 12.0
FOLLOW_DISTANCE_QUERY_TIMEOUT_SECONDS = 0.75
FOLLOW_LOST_TARGET_TIMEOUT_SECONDS = 1.5
FOLLOW_REACQUIRE_SETTLE_SECONDS = 0.75
FOLLOW_CONFIDENCE_THRESHOLD = 0.90
FOLLOW_CAMERA_INDEX = 0
FOLLOW_TARGET_LABEL = "person"
FOLLOW_COMMAND_PHRASES = ("follow me",)
FOLLOW_SERVO_CENTER_ANGLE = 90
FOLLOW_SERVO_LEFT_ANGLE = 150
FOLLOW_SERVO_RIGHT_ANGLE = 30
FOLLOW_SCAN_ANGLES = (
    FOLLOW_SERVO_CENTER_ANGLE,
    120,
    FOLLOW_SERVO_LEFT_ANGLE,
    120,
    FOLLOW_SERVO_CENTER_ANGLE,
    60,
    FOLLOW_SERVO_RIGHT_ANGLE,
    60,
    FOLLOW_SERVO_CENTER_ANGLE,
)
FOLLOW_SERVO_ALIGN_DEADZONE_DEGREES = 8
FOLLOW_INITIAL_ALIGN_STEP_DEGREES = 15
FOLLOW_SHOW_WINDOW = True
FOLLOW_WINDOW_NAME = "Nova Follow"
TRACKER_DEADZONE_RATIO = 0.2
TRACKER_SMALL_STEP = 7
TRACKER_LARGE_STEP = 15
TRACKER_COMMAND_COOLDOWN = 0.2
TRACKER_CONFIRM_FRAMES = 2

PRESET_GREETING_RESPONSES = {
    "good morning": "Good morning",
    "hello": "Hello I'm NOVA",
}


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


class TrackedPersonMonitor:
    """Background person tracker with always-on preview window."""

    def __init__(self, send_payload, model_path: str) -> None:
        self._send_payload = send_payload
        self._model_path = model_path
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_angle = FOLLOW_SERVO_CENTER_ANGLE
        self._state_lock = threading.Lock()
        self._current_detection: Detection | None = None
        self._frame_width = 0
        self._frame_height = 0

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="motor-follow-tracker")
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

    def get_snapshot(self) -> tuple[Detection | None, int, int]:
        with self._state_lock:
            return self._current_detection, self._frame_width, self._frame_height

    def _run(self) -> None:
        if cv2 is None or YOLO is None:
            print("[FollowTracker] opencv-python and ultralytics are required; tracking disabled.")
            return

        try:
            model = YOLO(self._model_path)
        except Exception as exc:
            print(f"[FollowTracker] Could not load YOLO model: {exc}")
            return

        capture = cv2.VideoCapture(FOLLOW_CAMERA_INDEX)
        if not capture.isOpened():
            capture.release()
            print("[FollowTracker] Could not open camera; tracking disabled.")
            return

        last_command_time = 0.0
        candidate_adjustment = 0
        candidate_frames = 0

        try:
            self._send_angle(self._current_angle)
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue

                results = model(frame, verbose=False)
                detection = find_best_person_detection(results[0]) if results else None

                frame_height, frame_width = frame.shape[:2]
                with self._state_lock:
                    self._current_detection = detection
                    self._frame_width = frame_width
                    self._frame_height = frame_height

                status_text = "Tracking paused" if self._pause_event.is_set() else "Tracking active"
                if FOLLOW_SHOW_WINDOW and cv2 is not None:
                    preview = frame.copy()
                    annotate_follow_frame(preview, detection, status_text)
                    cv2.imshow(FOLLOW_WINDOW_NAME, preview)
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        self._stop_event.set()
                        break

                if self._pause_event.is_set():
                    time.sleep(0.05)
                    continue

                if detection is None:
                    candidate_adjustment = 0
                    candidate_frames = 0
                    time.sleep(0.05)
                    continue

                raw_adjustment = compute_servo_adjustment(frame_width, detection.center_x)
                if raw_adjustment == 0:
                    candidate_adjustment = 0
                    candidate_frames = 0
                    time.sleep(0.05)
                    continue

                direction = 1 if raw_adjustment > 0 else -1
                if direction == candidate_adjustment:
                    candidate_frames += 1
                else:
                    candidate_adjustment = direction
                    candidate_frames = 1

                if candidate_frames < TRACKER_CONFIRM_FRAMES:
                    time.sleep(0.05)
                    continue

                now = time.monotonic()
                if (now - last_command_time) < TRACKER_COMMAND_COOLDOWN:
                    time.sleep(0.05)
                    continue

                new_angle = self._current_angle + raw_adjustment
                new_angle = max(min(new_angle, FOLLOW_SERVO_LEFT_ANGLE + 10), FOLLOW_SERVO_RIGHT_ANGLE - 10)
                if new_angle != self._current_angle:
                    self._send_angle(new_angle)
                    self._current_angle = new_angle
                    last_command_time = now
                candidate_adjustment = 0
                candidate_frames = 0
                time.sleep(0.05)
        finally:
            capture.release()
            if FOLLOW_SHOW_WINDOW and cv2 is not None:
                cv2.destroyWindow(FOLLOW_WINDOW_NAME)

    def _send_angle(self, angle: int) -> None:
        self._send_payload(f"SV{angle}")


def compute_servo_adjustment(frame_width: int, center_x: float) -> int:
    midpoint = frame_width / 2.0
    offset = center_x - midpoint
    deadzone_half_width = (frame_width * TRACKER_DEADZONE_RATIO) / 2.0
    large_error_threshold = frame_width * 0.25

    if abs(offset) <= deadzone_half_width:
        return 0

    step = TRACKER_LARGE_STEP if abs(offset) >= large_error_threshold else TRACKER_SMALL_STEP
    return -step if offset > 0 else step


def _load_root_speech_module():
    """Load nova_testing/speech.py without shadowing motor config imports."""
    module_path = NOVA_TESTING_DIR / "speech.py"
    spec = importlib.util.spec_from_file_location("nova_testing_root_speech_preset", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load speech module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    previous_config = sys.modules.pop("config", None)
    sys.path.insert(0, str(NOVA_TESTING_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(NOVA_TESTING_DIR))
        except ValueError:
            pass
        if previous_config is not None:
            sys.modules["config"] = previous_config
        else:
            sys.modules.pop("config", None)
    return module


_ROOT_SPEECH = _load_root_speech_module()
speak_text = _ROOT_SPEECH.speak_text
warm_tts = _ROOT_SPEECH.warm_tts
_speech_sd = getattr(_ROOT_SPEECH, "sd", None)
_speech_np = getattr(_ROOT_SPEECH, "np", None)
_speech_sample_rate = getattr(_ROOT_SPEECH, "PIPER_SAMPLE_RATE", 22050)


def _play_silence(seconds: float) -> None:
    """Play silent audio to wake the speaker path before speech starts."""
    if seconds <= 0 or _speech_sd is None or _speech_np is None:
        return
    frames = max(1, int(_speech_sample_rate * seconds))
    silence = _speech_np.zeros(frames, dtype=_speech_np.int16)
    try:
        _speech_sd.play(silence, samplerate=_speech_sample_rate, blocking=True)
    except Exception as exc:
        print(f"[TTS] Silence preroll failed: {exc}")


def speak_blocking(text: str) -> None:
    """Speak through the existing nova_testing speech.py path and wait for completion."""
    if not text:
        return
    _play_silence(SPEECH_PREROLL_SECONDS)
    if not speak_text(text):
        print("[TTS] Speech output failed.")


def preset_response_for(command_text: str) -> str | None:
    normalized = normalize_text(command_text)
    for phrase, response in PRESET_GREETING_RESPONSES.items():
        if phrase in normalized:
            return response
    return None


def parse_follow_command(command_text: str) -> str | None:
    normalized = normalize_text(command_text)
    for phrase in FOLLOW_COMMAND_PHRASES:
        if phrase in normalized:
            return phrase
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


def find_best_person_detection(result) -> Detection | None:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return None

    best: Detection | None = None
    for box in boxes:
        confidence = float(box.conf[0])
        if confidence < FOLLOW_CONFIDENCE_THRESHOLD:
            continue
        label_index = int(box.cls[0])
        label = str(result.names.get(label_index, f"class_{label_index}")).strip().lower()
        if label != FOLLOW_TARGET_LABEL:
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


def annotate_follow_frame(frame, detection: Detection | None, status_text: str) -> None:
    """Annotate the live follow window with the current target and status."""
    if cv2 is None:
        return

    frame_height, frame_width = frame.shape[:2]
    midpoint = frame_width // 2
    deadzone_half_width = int((frame_width * FOLLOW_CENTER_DEADZONE_RATIO) / 2.0)

    cv2.line(frame, (midpoint, 0), (midpoint, frame_height), (255, 255, 0), 1)
    cv2.line(
        frame,
        (midpoint - deadzone_half_width, 0),
        (midpoint - deadzone_half_width, frame_height),
        (0, 255, 255),
        1,
    )
    cv2.line(
        frame,
        (midpoint + deadzone_half_width, 0),
        (midpoint + deadzone_half_width, frame_height),
        (0, 255, 255),
        1,
    )
    cv2.putText(frame, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 220, 50), 2)

    if detection is None:
        cv2.putText(
            frame,
            f"No person >= {FOLLOW_CONFIDENCE_THRESHOLD:.2f} confidence",
            (10, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (30, 30, 255),
            2,
        )
        return

    half_width = detection.width / 2.0
    half_height = detection.height / 2.0
    x1 = int(detection.center_x - half_width)
    y1 = int(detection.center_y - half_height)
    x2 = int(detection.center_x + half_width)
    y2 = int(detection.center_y + half_height)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
    label_text = f"{detection.label} {detection.confidence:.2f}"
    cv2.putText(frame, label_text, (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)


def run_follow_mode(send_payload, get_current_servo_angle, read_distance_inches, tracker: TrackedPersonMonitor) -> None:
    """Follow the person already in frame instead of rotating to search for one."""
    last_detection_time = time.monotonic()
    scan_index = 0
    print("[Follow] Entered follow mode")
    initial_detection, initial_width, initial_height = tracker.get_snapshot()
    if initial_detection is None or initial_width <= 0 or initial_height <= 0:
        print("[Follow] No person currently in frame. Aborting follow mode.")
        return

    locked_servo_angle = get_current_servo_angle()
    print(f"[Follow] Starting from tracked servo angle: {locked_servo_angle}")

    send_payload("LOOK_CENTER")
    time.sleep(0.3)

    while True:
        detection, frame_width, frame_height = tracker.get_snapshot()
        now = time.monotonic()
        distance_inches = read_distance_inches()

        if distance_inches is not None and distance_inches <= FOLLOW_STOP_DISTANCE_INCHES:
            print(f"[Follow] Reached stop distance ({distance_inches:.1f} in). Stopping.")
            send_payload("X")
            break

        if detection is None:
            if last_detection_time and (now - last_detection_time) >= FOLLOW_LOST_TARGET_TIMEOUT_SECONDS:
                target_angle = FOLLOW_SCAN_ANGLES[scan_index % len(FOLLOW_SCAN_ANGLES)]
                scan_index += 1
                print(f"[Follow] Lost person target. Scanning at servo angle {target_angle}.")
                send_payload(f"SV{target_angle}")
                time.sleep(FOLLOW_REACQUIRE_SETTLE_SECONDS)
                continue
            time.sleep(0.1)
            continue

        last_detection_time = now
        scan_index = 0

        offset_ratio = (detection.center_x - (frame_width / 2.0)) / max(frame_width, 1)

        print(
            "[Follow] person"
            f" conf={detection.confidence:.2f}"
            f" offset_ratio={offset_ratio:.2f}"
            f" distance_inches={distance_inches if distance_inches is not None else 'unknown'}"
        )

        current_servo_angle = get_current_servo_angle()
        servo_error = current_servo_angle - FOLLOW_SERVO_CENTER_ANGLE
        if abs(servo_error) > FOLLOW_SERVO_ALIGN_DEADZONE_DEGREES:
            turn_payload = f"SL{FOLLOW_TURN_BURST_MS}" if servo_error > 0 else f"SR{FOLLOW_TURN_BURST_MS}"
            print(
                f"[Follow] Servo at {current_servo_angle}; "
                f"spinning base with {turn_payload} to realign before moving."
            )
            send_payload(turn_payload)
            time.sleep((FOLLOW_TURN_BURST_MS / 1000.0) + FOLLOW_SETTLE_SECONDS)
            send_payload("LOOK_CENTER")
            time.sleep(0.15)
            continue

        send_payload("LOOK_CENTER")
        time.sleep(0.1)

        print(f"[Follow] Advancing with F{FOLLOW_FORWARD_BURST_MS}")
        send_payload(f"F{FOLLOW_FORWARD_BURST_MS}")
        time.sleep((FOLLOW_FORWARD_BURST_MS / 1000.0) + FOLLOW_SETTLE_SECONDS)

    send_payload("LOOK_CENTER")


def run() -> None:
    """Run streaming passive listening with preset greeting speech."""
    os.chdir(MOTOR_DIR)
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
    current_servo_angle = {"value": FOLLOW_SERVO_CENTER_ANGLE}

    def send_payload(payload: str) -> bool:
        stripped = payload.strip().upper()
        if stripped == "LOOK_LEFT":
            current_servo_angle["value"] = FOLLOW_SERVO_LEFT_ANGLE
        elif stripped == "LOOK_RIGHT":
            current_servo_angle["value"] = FOLLOW_SERVO_RIGHT_ANGLE
        elif stripped == "LOOK_CENTER":
            current_servo_angle["value"] = FOLLOW_SERVO_CENTER_ANGLE
        elif stripped.startswith("SV"):
            try:
                current_servo_angle["value"] = int(stripped[2:])
            except ValueError:
                pass
        with serial_lock:
            return motor.send_message(payload)

    def send_led(token: str) -> bool:
        with serial_lock:
            return motor.set_led_state(token)

    def send_command(command: str) -> bool:
        with serial_lock:
            return motor.send_command(command)

    def get_current_servo_angle() -> int:
        return current_servo_angle["value"]

    def read_distance_inches() -> float | None:
        with serial_lock:
            response = motor.request_message(
                "DIST",
                expected_prefix="DIST",
                max_wait_seconds=FOLLOW_DISTANCE_QUERY_TIMEOUT_SECONDS,
            )
        if not response:
            print("[Follow] Ultrasonic distance query timed out")
            return None

        parts = response.split(maxsplit=1)
        if len(parts) != 2:
            print(f"[Follow] Unexpected distance response: {response}")
            return None

        value = parts[1].strip()
        if value.upper() == "ERR":
            print("[Follow] Ultrasonic distance read failed")
            return None

        try:
            return float(value)
        except ValueError:
            print(f"[Follow] Invalid distance value: {response}")
            return None

    yolo_model_path = NOVA_TESTING_DIR.parent / "yolo11n.pt"
    tracker = TrackedPersonMonitor(
        send_payload=send_payload,
        model_path=str(yolo_model_path) if yolo_model_path.exists() else "yolo11n.pt",
    )
    warm_tts()
    send_led(LED_IDLE)
    tracker.start()

    print("Motor follow started")
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
                print(f"Wake word detected: {WAKE_PHRASE} ({wake_hits}/{WAKE_REQUIRED_HITS})")
            else:
                wake_hits = 0

            if wake_hits >= WAKE_REQUIRED_HITS:
                wake_hits = 0
                previous_passive_text = ""
                send_led(LED_COMMAND)
                tracker.pause()
                try:
                    print("Listening for command...")
                    command_text = normalize_text(listener.listen_for_command(COMMAND_LISTEN_TIMEOUT_SECONDS))
                    if command_text:
                        print(f"Heard (command): {command_text}")

                    greeting = parse_greeting_command(command_text)
                    if greeting is not None:
                        print(f"Greeting recognized: {greeting}")
                        response = preset_response_for(command_text)
                        execute_greeting_sequence(send_payload)
                        if response is not None:
                            print(f"Nova preset response: {response}")
                            speak_blocking(response)
                        send_led(LED_IDLE)
                        previous_passive_text = ""
                        continue

                    follow_phrase = parse_follow_command(command_text)
                    if follow_phrase is not None:
                        print(f"Follow command recognized: {follow_phrase}")
                        try:
                            run_follow_mode(send_payload, get_current_servo_angle, read_distance_inches, tracker)
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
                finally:
                    tracker.resume()

            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down motor follow")
    finally:
        tracker.stop()
        send_led(LED_IDLE)
        motor.close()
        listener.stop()


if __name__ == "__main__":
    run()
