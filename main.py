"""Main runtime loop for NOVA vision -> LLM -> Piper speech."""

from __future__ import annotations

import queue
import threading
import time

from config import (
    CV_CONFIDENCE_THRESHOLD,
    CV_ENABLED,
    FRAME_SAMPLE_COUNT,
    FRAME_SAMPLE_INTERVAL_SECONDS,
    MAX_PENDING_TTS_RESPONSES,
    PIPELINE_LOOP_DELAY_SECONDS,
    SPEECH_ENABLED,
)
from llm import generate_scene_response, warm_llm
from speech import speak_text, warm_tts
from vision import get_scene_text_burst


def _replace_queue_item(target_queue: queue.Queue[str], value: str) -> None:
    """Keep only the newest queued item to avoid speech backlog."""
    while True:
        try:
            target_queue.get_nowait()
        except queue.Empty:
            break
    target_queue.put_nowait(value)


def _speech_worker(target_queue: queue.Queue[str], stop_event: threading.Event) -> None:
    """Speak responses asynchronously until stop requested."""
    while not stop_event.is_set():
        try:
            text = target_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        if not text:
            continue
        if not speak_text(text):
            print("[TTS] Speech output failed.")


def run() -> None:
    """Run continuous loop: capture burst -> summarize -> LLM -> speak."""
    print("NOVA continuous vision shell")
    print("Pipeline: 3 frames (1/sec) -> scene summary -> LLM -> Piper speech")
    print("Press Ctrl+C to quit.\n")

    if not CV_ENABLED:
        print("[CV] Disabled in config; this mode requires CV_ENABLED=True.")
        return

    warm_llm()
    if SPEECH_ENABLED:
        warm_tts()

    speech_queue: queue.Queue[str] = queue.Queue(maxsize=max(1, MAX_PENDING_TTS_RESPONSES))
    stop_event = threading.Event()
    speech_thread: threading.Thread | None = None

    if SPEECH_ENABLED:
        speech_thread = threading.Thread(
            target=_speech_worker,
            args=(speech_queue, stop_event),
            daemon=True,
            name="speech-worker",
        )
        speech_thread.start()

    try:
        while True:
            cycle_start = time.time()

            scene_text, per_frame_detections, aggregated = get_scene_text_burst(
                frame_count=FRAME_SAMPLE_COUNT,
                interval_seconds=FRAME_SAMPLE_INTERVAL_SECONDS,
                confidence_threshold=CV_CONFIDENCE_THRESHOLD,
            )

            frame_counts = [len(frame) for frame in per_frame_detections]
            print(f"[CV] Frame detections: {frame_counts}")
            print(f"[CV] Burst summary: {scene_text}")
            if aggregated:
                print(f"[CV] Aggregated: {aggregated}")

            response = generate_scene_response(scene_text)
            print(f"Nova: {response}\n")

            if not response.startswith("[LLM ERROR]") and SPEECH_ENABLED:
                _replace_queue_item(speech_queue, response)

            elapsed = time.time() - cycle_start
            if PIPELINE_LOOP_DELAY_SECONDS > elapsed:
                time.sleep(PIPELINE_LOOP_DELAY_SECONDS - elapsed)
    except KeyboardInterrupt:
        print("\nExiting NOVA.")
    finally:
        stop_event.set()
        if speech_thread is not None:
            speech_thread.join(timeout=2)


if __name__ == "__main__":
    run()
