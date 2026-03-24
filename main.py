"""Main runtime loop for NOVA multimodal prototype."""

from __future__ import annotations

from config import (
    CV_CONFIDENCE_THRESHOLD,
    CV_ENABLED,
    SPEECH_ENABLED,
    STT_ENABLED,
)
from llm import generate_multimodal_response, warm_llm
from speech import speak_text, warm_tts
from stt import STTRecognizer, create_recognizer
from vision import get_scene_text


def _read_terminal_input() -> str | None:
    """Read fallback terminal input."""
    try:
        text = input("You (typed): ").strip()
    except (EOFError, KeyboardInterrupt):
        return "exit"
    return text or None


def _initialize_stt() -> STTRecognizer | None:
    """Create STT recognizer when enabled."""
    if not STT_ENABLED:
        print("[STT] Disabled.")
        return None
    try:
        recognizer = create_recognizer()
        print("[STT] Ready.")
        return recognizer
    except Exception as exc:
        print(f"[STT] Initialization failed: {exc}")
        return None


def _get_user_text(stt_recognizer: STTRecognizer | None) -> str | None:
    """Get user text from STT when possible, otherwise terminal input."""
    if stt_recognizer is not None:
        print("\nListening...")
        spoken_text = stt_recognizer.listen_for_utterance()
        if spoken_text:
            print(f"You (spoken): {spoken_text}")
            return spoken_text
        print("[STT] No clear utterance detected.")
    return _read_terminal_input()


def _get_scene_text() -> str | None:
    """Fetch current scene summary from vision pipeline."""
    if not CV_ENABLED:
        return None
    try:
        scene_text, detections = get_scene_text(confidence_threshold=CV_CONFIDENCE_THRESHOLD)
        print(f"[CV] Detections: {detections if detections else '[]'}")
        print(f"[CV] Scene: {scene_text}")
        return scene_text
    except Exception as exc:
        print(f"[CV] Failed: {exc}")
        return None


def run() -> None:
    """Run NOVA multimodal loop: STT + CV -> LLM -> TTS."""
    print("NOVA multimodal test shell")
    print("Pipeline: STT + CV -> LLM -> TTS")
    print("Type 'exit' in typed fallback input to quit.\n")

    warm_llm()
    if SPEECH_ENABLED:
        warm_tts()

    stt_recognizer = _initialize_stt()
    if STT_ENABLED and stt_recognizer is None:
        print("[STT] Falling back to terminal input.")

    while True:
        try:
            user_text = _get_user_text(stt_recognizer)
            if not user_text:
                continue
            if user_text.lower() in {"exit", "quit"}:
                print("Exiting NOVA.")
                break

            scene_text = _get_scene_text()
            response = generate_multimodal_response(user_text, scene_text)
            print(f"Nova: {response}\n")

            if response.startswith("[LLM ERROR]"):
                continue
            if SPEECH_ENABLED and not speak_text(response):
                print("[TTS] Speech output failed.\n")
        except KeyboardInterrupt:
            print("\nExiting NOVA.")
            break
        except Exception as exc:
            print(f"[MAIN] Unexpected runtime error: {exc}")


if __name__ == "__main__":
    run()

