"""Streaming Vosk motor voice demo with background servo tracking."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from collections import deque
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
from servo_tracking import ServoPersonTracker  # noqa: E402

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - environment dependent
    sd = None

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except ImportError:  # pragma: no cover - environment dependent
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None


LED_IDLE = "LED_READY"
LED_COMMAND = "LED_LISTEN"

VOSK_MODEL_PATH = os.getenv("NOVA_VOSK_MODEL_PATH", "vosk-model-small-en-us-0.15")
STT_SAMPLE_RATE = int(os.getenv("NOVA_VOSK_SAMPLE_RATE", "16000"))
STT_BLOCK_SIZE = int(os.getenv("NOVA_VOSK_BLOCK_SIZE", "8000"))
STT_DEBUG = os.getenv("NOVA_STT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
MIC_DEVICE_INDEX = (
    int(os.getenv("NOVA_MIC_DEVICE_INDEX", "").strip())
    if os.getenv("NOVA_MIC_DEVICE_INDEX", "").strip()
    else None
)


class ContinuousVoskListener:
    """Always-on microphone stream with blocking wake and command helpers."""

    def __init__(self) -> None:
        self._model_path = Path(VOSK_MODEL_PATH)
        self._sample_rate = STT_SAMPLE_RATE
        self._block_size = STT_BLOCK_SIZE
        self._device_index = MIC_DEVICE_INDEX
        self._debug = STT_DEBUG

        self._model: Model | None = None
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=64)
        self._stream = None
        self._started = False

    def validate_environment(self) -> tuple[bool, str]:
        if sd is None:
            return False, "Missing dependency: sounddevice is not installed"
        if Model is None or KaldiRecognizer is None:
            return False, "Missing dependency: vosk is not installed"
        if not self._model_path.exists():
            return False, f"Missing Vosk model path: {self._model_path}"
        return True, ""

    def start(self) -> bool:
        ok, message = self.validate_environment()
        if not ok:
            print(message)
            return False

        try:
            if SetLogLevel is not None:
                SetLogLevel(-1)
            self._model = Model(str(self._model_path))
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=self._block_size,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
                device=self._device_index,
            )
            self._stream.start()
            self._started = True
            if self._debug:
                print(f"[STT DEBUG] Listening on mic device index: {self._device_index}")
            return True
        except Exception as exc:
            print(f"Audio stream start failure: {exc}")
            self.stop()
            return False

    def stop(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        finally:
            self._stream = None
            self._started = False
            self._clear_audio_queue()

    def listen_for_passive_trigger(self) -> str:
        recognizer = self._new_recognizer()
        recent_segments: deque[str] = deque(maxlen=4)

        while self._started:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(chunk):
                text = self._extract_text(recognizer.Result())
                if text:
                    if self._debug:
                        print(f"[STT DEBUG] final: {text}")
                    recent_segments.append(text)
                    combined = normalize_text(" ".join(recent_segments))
                    if contains_emergency_stop(combined) or contains_wake_phrase(combined):
                        return combined
            else:
                partial = self._extract_text(recognizer.PartialResult(), key="partial")
                if partial:
                    if self._debug:
                        print(f"[STT DEBUG] partial: {partial}")
                    combined = normalize_text(" ".join([*recent_segments, partial]))
                    if contains_emergency_stop(combined) or contains_wake_phrase(combined):
                        return combined

        return ""

    def listen_for_command(self, timeout_seconds: float) -> str:
        recognizer = self._new_recognizer()
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        best_final = ""
        best_partial = ""
        speech_started = False
        last_voice_time = time.monotonic()

        while self._started and time.monotonic() < deadline:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(chunk):
                text = self._extract_text(recognizer.Result())
                if text:
                    if self._debug:
                        print(f"[STT DEBUG] command final: {text}")
                    best_final = text
                    speech_started = True
                    last_voice_time = time.monotonic()
            else:
                partial = self._extract_text(recognizer.PartialResult(), key="partial")
                if partial:
                    if self._debug:
                        print(f"[STT DEBUG] command partial: {partial}")
                    best_partial = partial
                    speech_started = True
                    last_voice_time = time.monotonic()
                elif speech_started and (time.monotonic() - last_voice_time) > 0.6:
                    break

        final_text = self._extract_text(recognizer.FinalResult())
        if final_text:
            best_final = final_text

        return normalize_text(best_final or best_partial)

    def _audio_callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            return
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

    def _new_recognizer(self) -> KaldiRecognizer:
        if self._model is None:
            raise RuntimeError("Speech listener has not been started.")
        return KaldiRecognizer(self._model, self._sample_rate)

    def _clear_audio_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def _extract_text(raw_json: str, key: str = "text") -> str:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            return ""
        return normalize_text(str(parsed.get(key, "")).strip())


def execute_greeting_sequence(send_payload) -> None:
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


def run() -> None:
    os.chdir(MOTOR_DIR)
    listener = ContinuousVoskListener()
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

    def send_payload(payload: str) -> bool:
        with serial_lock:
            return motor.send_message(payload)

    def send_led(token: str) -> bool:
        with serial_lock:
            return motor.set_led_state(token)

    def send_command(command: str) -> bool:
        with serial_lock:
            return motor.send_command(command)

    yolo_model_path = NOVA_TESTING_DIR.parent / "yolo11n.pt"
    tracker = ServoPersonTracker(
        send_payload=send_payload,
        model_path=str(yolo_model_path) if yolo_model_path.exists() else "yolo11n.pt",
    )

    send_led(LED_IDLE)
    tracker.start()

    print("Streaming Vosk motor voice demo started")
    print("Pipeline: Vosk streaming wake/command listener + servo tracking + serial motor control")
    print(f"Wake phrase: {WAKE_PHRASE}")
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
                print("Listening for command...")
                command_text = normalize_text(listener.listen_for_command(COMMAND_LISTEN_TIMEOUT_SECONDS))
                if command_text:
                    print(f"Heard (command): {command_text}")

                greeting = parse_greeting_command(command_text)
                if greeting is not None:
                    print(f"Greeting recognized: {greeting}")
                    tracker.pause()
                    try:
                        execute_greeting_sequence(send_payload)
                    finally:
                        tracker.resume()
                    send_led(LED_IDLE)
                    continue

                parsed = parse_motor_command(command_text)
                if parsed is None:
                    print("No valid command recognized")
                    send_led(LED_IDLE)
                    continue

                phrase, serial_command, duration_ms = parsed
                print(f"Command recognized: {phrase}")
                payload = serial_command if duration_ms is None else f"{serial_command}{duration_ms}"
                print(f"Sending motion payload: {payload}")
                send_payload(payload)
                if duration_ms is None:
                    send_led(LED_IDLE)
                continue

            previous_passive_text = current_passive_text if current_passive_text else ""
    except KeyboardInterrupt:
        print("\nShutting down streaming Vosk motor voice demo")
    finally:
        tracker.stop()
        send_led(LED_IDLE)
        motor.close()
        listener.stop()


if __name__ == "__main__":
    run()
