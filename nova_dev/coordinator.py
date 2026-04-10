"""Coordinator entrypoint for the Nova integrated runtime."""

from __future__ import annotations

import time
from queue import Empty, Queue

from audio_service import AudioService
from config import RuntimeConfig
from events import Event, EventType
from llm_service import LLMService
from motion_service import ArduinoSerialClient, MotionService
from robot_state import RobotState
from servo_service import ServoService
from tts_service import TTSService
from vision_service import VisionService


class Coordinator:
    """Single-process event-driven coordinator for Nova."""

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.event_queue: Queue[Event] = Queue()
        self.state = RobotState.OBSERVE
        self.latest_scene_text = "Scene unavailable."
        self.latest_detections: list[dict] = []
        self._last_cv_cycle = 0.0

        self.serial_client = ArduinoSerialClient(
            port=self.config.serial_port,
            baud_rate=self.config.baud_rate,
            timeout_seconds=self.config.serial_timeout_seconds,
        )
        self.audio_service = AudioService(self.event_queue, self.config)
        self.vision_service = VisionService(self.event_queue, self.config)
        self.motion_service = MotionService(self.event_queue, self.config, self.serial_client)
        self.servo_service = ServoService(self.event_queue, self.config, self.serial_client)
        self.tts_service = TTSService(self.event_queue, self.config)
        self.llm_service = LLMService(self.config)

    def start(self) -> None:
        if not self.motion_service.connect():
            raise RuntimeError("Could not connect to Arduino serial.")

        self.motion_service.set_led_state("LED_READY")
        if self.config.speech_enabled:
            self.audio_service.start()
        if self.config.cv_enabled:
            self.vision_service.start()
        if self.config.tts_enabled:
            self.tts_service.warm()
        self.llm_service.warm()

        self.state = RobotState.OBSERVE
        print(f"[Coordinator] Started in state: {self.state.value}")

    def shutdown(self) -> None:
        self.motion_service.set_led_state("LED_READY")
        self.motion_service.close()
        self.audio_service.stop()
        self.vision_service.stop()

    def handle_event(self, event: Event) -> None:
        print(f"[Event] {event.type.value} from {event.source}: {event.payload}")

        if event.type == EventType.ERROR:
            self.state = RobotState.ERROR
            print(f"[Coordinator] Error: {event.payload}")
            return

        if event.type == EventType.EMERGENCY_STOP:
            self.motion_service.emergency_stop()
            self.state = RobotState.PAUSED_FOR_SAFETY
            self.vision_service.pause_inference()
            self.motion_service.set_led_state("LED_ERROR")
            print("[Coordinator] Emergency stop. Vision paused.")
            return

        if event.type == EventType.WAKE_DETECTED:
            self.state = RobotState.COMMAND_MODE
            self.vision_service.pause_inference()
            self.motion_service.set_led_state("LED_LISTEN")
            print("[Coordinator] Entered command mode.")
            self.audio_service.capture_command()
            return

        if event.type == EventType.COMMAND_RECEIVED:
            transcript = str(event.payload.get("transcript", "")).strip()
            plan = self.llm_service.plan_from_command(transcript, self.latest_scene_text)
            self._execute_plan(plan)
            return

        if event.type == EventType.MOTION_STARTED:
            self.state = RobotState.EXECUTING_MOTION
            self.motion_service.set_led_state("LED_MOVE")
            return

        if event.type == EventType.MOTION_COMPLETED:
            self.state = RobotState.OBSERVE
            self.vision_service.resume_inference()
            self.motion_service.set_led_state("LED_READY")
            print("[Coordinator] Motion completed. Returning to observe.")
            return

        if event.type == EventType.SERVO_COMPLETED:
            self.state = RobotState.OBSERVE
            self.vision_service.resume_inference()
            self.motion_service.set_led_state("LED_READY")
            return

        if event.type == EventType.TTS_STARTED:
            self.state = RobotState.SPEAKING
            return

        if event.type == EventType.TTS_FINISHED:
            self.state = RobotState.OBSERVE
            self.vision_service.resume_inference()
            self.motion_service.set_led_state("LED_READY")
            print("[Coordinator] Speech completed. Returning to observe.")
            return

        if event.type == EventType.VISION_DETECTION:
            self.latest_scene_text = str(event.payload.get("scene_text", self.latest_scene_text))
            self.latest_detections = list(event.payload.get("detections", []))
            return

        if event.type == EventType.VISION_TARGET_LOST:
            self.latest_scene_text = "I do not detect any clear objects in the recent frames."
            self.latest_detections = []
            return

    def _execute_plan(self, plan: dict) -> None:
        plan_type = plan.get("type")
        if plan_type == "motion":
            action = str(plan.get("action", "unknown"))
            duration_ms = plan.get("duration_ms")
            if duration_ms:
                payload = self._build_timed_motion_payload(action, int(duration_ms))
                if payload is not None:
                    self.motion_service.execute_payload(action, payload)
                    return
            self.motion_service.execute(action)
            return

        if plan_type == "servo_named":
            action = str(plan.get("action", "look_center"))
            if action == "look_left":
                self.servo_service.look_left()
            elif action == "look_right":
                self.servo_service.look_right()
            else:
                self.servo_service.look_center()
            return

        if plan_type == "speak":
            text = str(plan.get("text", "")).strip()
            if text:
                self.tts_service.speak(text)
            return

        print("[Coordinator] No action taken.")
        self.state = RobotState.OBSERVE
        self.vision_service.resume_inference()
        self.motion_service.set_led_state("LED_READY")

    def _build_timed_motion_payload(self, action: str, duration_ms: int) -> str | None:
        prefix_map = {
            "forward": "F",
            "backward": "B",
            "turn_left": "L",
            "turn_right": "R",
            "u_turn_left": "L",
            "u_turn_right": "R",
            "spin_left": "SL",
            "spin_right": "SR",
        }
        prefix = prefix_map.get(action)
        if prefix is None:
            return None
        return f"{prefix}{duration_ms}"

    def _drain_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except Empty:
                break
            self.handle_event(event)

    def _maybe_run_cv_cycle(self) -> None:
        if not self.config.cv_enabled or not self.vision_service.inference_enabled:
            return
        now = time.monotonic()
        if now - self._last_cv_cycle < self.config.cv_cycle_interval_seconds:
            return
        self._last_cv_cycle = now
        try:
            scene_text, detections = self.vision_service.sample_scene()
        except Exception as exc:
            print(f"[Vision] Error: {exc}")
            return
        self.latest_scene_text = scene_text
        self.latest_detections = detections
        print(f"[Vision] {scene_text}")

    def run_forever(self) -> None:
        self.start()
        try:
            while True:
                self._drain_events()

                if self.state == RobotState.OBSERVE and self.config.speech_enabled:
                    self.audio_service.poll_passive()
                    self._drain_events()

                if self.state == RobotState.OBSERVE:
                    self._maybe_run_cv_cycle()

                time.sleep(self.config.observe_loop_delay_seconds)
        except KeyboardInterrupt:
            print("\n[Coordinator] Stopped.")
        finally:
            self.shutdown()


def main() -> None:
    coordinator = Coordinator()
    coordinator.run_forever()


if __name__ == "__main__":
    main()
