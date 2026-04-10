"""Vision service wrapper for camera capture and inference."""

from __future__ import annotations

import time
from collections import defaultdict
from queue import Queue

from config import RuntimeConfig
from events import Event, EventType

try:
    import cv2
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - environment dependent
    YOLO = None


class VisionService:
    """Lightweight burst-based CV service."""

    def __init__(self, event_queue: Queue[Event], config: RuntimeConfig) -> None:
        self._event_queue = event_queue
        self._config = config
        self._capture_enabled = False
        self._inference_enabled = False
        self._model = None

    def start(self) -> None:
        if cv2 is None or YOLO is None:
            raise RuntimeError("opencv-python and ultralytics are required for vision.")
        self._model = YOLO(self._config.yolo_model_path)
        self._capture_enabled = True
        self._inference_enabled = True

    def stop(self) -> None:
        self._capture_enabled = False
        self._inference_enabled = False

    def pause_inference(self) -> None:
        self._inference_enabled = False

    def resume_inference(self) -> None:
        self._inference_enabled = True

    @property
    def inference_enabled(self) -> bool:
        return self._inference_enabled

    def sample_scene(self) -> tuple[str, list[dict]]:
        if not (self._capture_enabled and self._inference_enabled):
            return "Vision paused.", []

        frames = self._capture_burst()
        aggregated = self._aggregate_detections([self._detect(frame) for frame in frames])
        scene_text = self._build_scene_text(aggregated, total_frames=max(len(frames), self._config.frame_sample_count))

        if aggregated:
            top = aggregated[0]
            self._event_queue.put(
                Event(type=EventType.VISION_DETECTION, source="vision", payload={"detections": aggregated, "scene_text": scene_text})
            )
            if top.get("label") == self._config.target_label:
                return scene_text, aggregated
        else:
            self._event_queue.put(Event(type=EventType.VISION_TARGET_LOST, source="vision"))
        return scene_text, aggregated

    def _capture_burst(self) -> list:
        frames = []
        cap = cv2.VideoCapture(self._config.camera_index)
        if not cap.isOpened():
            cap.release()
            return frames
        try:
            for index in range(self._config.frame_sample_count):
                ok, frame = cap.read()
                if ok and frame is not None:
                    frames.append(frame)
                if index < self._config.frame_sample_count - 1 and self._config.frame_sample_interval_seconds > 0:
                    time.sleep(self._config.frame_sample_interval_seconds)
        finally:
            cap.release()
        return frames

    def _detect(self, frame) -> list[dict]:
        if frame is None:
            return []
        results = self._model(frame, verbose=False)
        detections: list[dict] = []
        for result in results:
            names = result.names
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                confidence = float(box.conf[0])
                if confidence < self._config.cv_confidence_threshold:
                    continue
                label_index = int(box.cls[0])
                label = str(names.get(label_index, f"class_{label_index}")).lower().strip()
                detections.append({"label": label, "confidence": round(confidence, 2)})
        return detections

    def _aggregate_detections(self, per_frame_detections: list[list[dict]]) -> list[dict]:
        frame_hits: dict[str, int] = defaultdict(int)
        best_confidence: dict[str, float] = defaultdict(float)
        for frame_detections in per_frame_detections:
            labels_in_frame: set[str] = set()
            for item in frame_detections:
                label = str(item.get("label", "")).strip().lower()
                if not label:
                    continue
                labels_in_frame.add(label)
                confidence = float(item.get("confidence", 0.0))
                if confidence > best_confidence[label]:
                    best_confidence[label] = confidence
            for label in labels_in_frame:
                frame_hits[label] += 1
        merged = [
            {"label": label, "confidence": round(best_confidence[label], 2), "frames_seen": hits}
            for label, hits in frame_hits.items()
        ]
        merged.sort(key=lambda d: (-d["frames_seen"], -d["confidence"], d["label"]))
        return merged

    def _build_scene_text(self, detections: list[dict], total_frames: int) -> str:
        if not detections:
            return "I do not detect any clear objects in the recent frames."
        parts = [f"{item['label']} ({item['frames_seen']}/{total_frames} frames)" for item in detections]
        if len(parts) == 1:
            joined = parts[0]
        elif len(parts) == 2:
            joined = f"{parts[0]} and {parts[1]}"
        else:
            joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"
        return f"In the last {total_frames} frames, I detected {joined}."
