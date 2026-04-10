"""Coordinator entrypoint for the Nova integrated runtime."""

from __future__ import annotations

from queue import Empty, Queue

from audio_service import AudioService
from config import RuntimeConfig
from events import Event, EventType
from llm_service import LLMService
from motion_service import MotionService
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

        self.audio_service = AudioService(self.event_queue)
        self.vision_service = VisionService(self.event_queue)
        self.motion_service = MotionService(self.event_queue)
        self.servo_service = ServoService(self.event_queue)
        self.tts_service = TTSService(self.event_queue)
        self.llm_service = LLMService()

    def start(self) -> None:
        """Start the coordinated runtime."""
        self.audio_service.start()
        if self.config.cv_enabled:
            self.vision_service.start()
        self.state = RobotState.OBSERVE
        print(f"[Coordinator] Started in state: {self.state.value}")

    def handle_event(self, event: Event) -> None:
        """Apply coordinator rules for one incoming event."""
        print(f"[Event] {event.type.value} from {event.source}: {event.payload}")

        if event.type == EventType.EMERGENCY_STOP:
            self.state = RobotState.PAUSED_FOR_SAFETY
            self.vision_service.pause_inference()
            print("[Coordinator] Emergency stop. Vision paused.")
            return

        if event.type == EventType.WAKE_DETECTED:
            self.state = RobotState.COMMAND_MODE
            self.vision_service.pause_inference()
            print("[Coordinator] Entered command mode.")
            return

        if event.type == EventType.COMMAND_RECEIVED:
            transcript = str(event.payload.get("transcript", "")).strip()
            plan = self.llm_service.plan_from_command(transcript)
            self._execute_plan(plan)
            return

        if event.type == EventType.MOTION_STARTED:
            self.state = RobotState.EXECUTING_MOTION
            return

        if event.type == EventType.MOTION_COMPLETED:
            self.state = RobotState.OBSERVE
            self.vision_service.resume_inference()
            print("[Coordinator] Motion completed. Returning to observe.")
            return

        if event.type == EventType.TTS_STARTED:
            self.state = RobotState.SPEAKING
            return

        if event.type == EventType.TTS_FINISHED:
            self.state = RobotState.OBSERVE
            self.vision_service.resume_inference()
            print("[Coordinator] Speech completed. Returning to observe.")
            return

    def _execute_plan(self, plan: dict) -> None:
        plan_type = plan.get("type")
        if plan_type == "motion":
            self.motion_service.execute(str(plan.get("action", "unknown")))
            return
        if plan_type == "servo":
            action = str(plan.get("action", ""))
            if action == "look_left":
                self.servo_service.set_angle(150)
            elif action == "look_right":
                self.servo_service.set_angle(30)
            else:
                self.servo_service.set_angle(90)
            self.state = RobotState.OBSERVE
            self.vision_service.resume_inference()
            return
        if plan_type == "speak":
            self.tts_service.speak(str(plan.get("text", "")))
            return
        print("[Coordinator] No action taken.")

    def run_forever(self) -> None:
        """Process events until interrupted."""
        self.start()
        try:
            while True:
                try:
                    event = self.event_queue.get(timeout=self.config.queue_poll_timeout_seconds)
                except Empty:
                    continue
                self.handle_event(event)
        except KeyboardInterrupt:
            print("\n[Coordinator] Stopped.")


def main() -> None:
    coordinator = Coordinator()
    coordinator.run_forever()


if __name__ == "__main__":
    main()
