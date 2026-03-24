"""Terminal test harness for NOVA chat mode and CV scene mode."""

from __future__ import annotations

from llm import generate_response, generate_scene_response
from speech import speak_text
from vision import build_scene_text, capture_frame, detect_objects

SPEECH_ENABLED = True
CAMERA_INDEX = 0
CONFIDENCE_THRESHOLD = 0.5
FRAME_COUNT = 5
YOLO_MODEL_PATH = "yolo11n.pt"


def run_chat_mode() -> None:
    """Run an interactive terminal chat loop."""
    print("\nNOVA Chat Mode")
    print("Type messages to chat with Nova.")
    print("Type 'exit' or 'quit' to close.\n")

    while True:
        try:
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting NOVA test shell.")
            break

        text = user_input.strip()
        if not text:
            print("Nova: Please type a message.\n")
            continue
        if text.lower() in {"exit", "quit"}:
            print("Exiting NOVA test shell.")
            break

        response = generate_response(text)
        print(f"Nova: {response}\n")

        if response.startswith("[LLM ERROR]"):
            continue

        if SPEECH_ENABLED and not speak_text(response):
            print("[TTS WARNING] Could not speak response. Check Piper/aplay or espeak fallback.\n")


def run_cv_scene_mode() -> None:
    """Capture frames, detect objects, summarize scene, and query LLM."""
    print("\nNOVA CV Scene Test Mode")
    print(
        f"Config: camera_index={CAMERA_INDEX}, frame_count={FRAME_COUNT}, "
        f"confidence_threshold={CONFIDENCE_THRESHOLD}, speech_enabled={SPEECH_ENABLED}"
    )
    print("Capturing frames...\n")

    aggregated: dict[str, float] = {}

    for index in range(1, FRAME_COUNT + 1):
        try:
            frame = capture_frame(camera_index=CAMERA_INDEX)
        except Exception as exc:
            print(f"[VISION ERROR] Webcam capture failed: {exc}")
            return

        if frame is None:
            print(f"[VISION WARNING] Frame {index}: capture failed.")
            continue

        try:
            detections = detect_objects(
                frame,
                confidence_threshold=CONFIDENCE_THRESHOLD,
                model_path=YOLO_MODEL_PATH,
            )
        except Exception as exc:
            print(f"[VISION ERROR] Detection failed on frame {index}: {exc}")
            return

        print(f"Frame {index}: {detections if detections else '[]'}")
        for item in detections:
            label = item["label"]
            conf = item["confidence"]
            if label not in aggregated or conf > aggregated[label]:
                aggregated[label] = conf

    final_detections = [
        {"label": label, "confidence": round(conf, 2)}
        for label, conf in aggregated.items()
    ]
    final_detections.sort(key=lambda d: (-d["confidence"], d["label"]))

    print(f"\nMerged detections: {final_detections if final_detections else '[]'}")
    scene_text = build_scene_text(final_detections)
    print(f"Scene text: {scene_text}")

    response = generate_scene_response(scene_text)
    print(f"Nova: {response}\n")

    if response.startswith("[LLM ERROR]"):
        return
    if SPEECH_ENABLED and not speak_text(response):
        print("[TTS WARNING] Could not speak response. Check Piper/aplay or espeak fallback.\n")


def run_menu() -> None:
    """Show mode menu and run selected test mode."""
    print("NOVA LLM + TTS + CV test shell")
    print("Choose a mode:")
    print("1) Chat mode")
    print("2) CV scene test mode")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            choice = input("Select mode (1/2/exit): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting NOVA test shell.")
            return

        if choice in {"exit", "quit"}:
            print("Exiting NOVA test shell.")
            return
        if choice == "1":
            run_chat_mode()
            return
        if choice == "2":
            run_cv_scene_mode()
            return
        print("Invalid selection. Enter 1, 2, or exit.\n")


if __name__ == "__main__":
    run_menu()
