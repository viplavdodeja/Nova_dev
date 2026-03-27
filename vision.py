"""Lightweight CV helpers for NOVA scene summaries."""

from __future__ import annotations

import time
from collections import defaultdict

from config import CAMERA_INDEX, CV_CONFIDENCE_THRESHOLD, YOLO_MODEL_PATH

try:
    import cv2
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - environment dependent
    YOLO = None

_MODEL = None


def _get_model(model_path: str = YOLO_MODEL_PATH):
    """Load YOLO model once and reuse it."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if YOLO is None:
        raise RuntimeError("ultralytics is not installed.")
    _MODEL = YOLO(model_path)
    return _MODEL


def capture_frame(camera_index: int = CAMERA_INDEX):
    """Capture one frame from webcam."""
    if cv2 is None:
        raise RuntimeError("opencv-python is not installed.")
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        return None
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def capture_frame_burst(
    frame_count: int,
    interval_seconds: float,
    camera_index: int = CAMERA_INDEX,
) -> list:
    """Capture a sequence of frames with a fixed delay between captures."""
    if frame_count <= 0:
        return []
    if cv2 is None:
        raise RuntimeError("opencv-python is not installed.")

    frames = []
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        return frames

    try:
        for index in range(frame_count):
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
            if index < frame_count - 1 and interval_seconds > 0:
                time.sleep(interval_seconds)
    finally:
        cap.release()
    return frames


def detect_objects(
    frame,
    confidence_threshold: float = CV_CONFIDENCE_THRESHOLD,
    model_path: str = YOLO_MODEL_PATH,
) -> list[dict]:
    """Run object detection and return deduplicated structured detections."""
    if frame is None:
        return []
    model = _get_model(model_path)
    results = model(frame, verbose=False)
    detections: list[dict] = []

    for result in results:
        names = result.names
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            confidence = float(box.conf[0])
            if confidence < confidence_threshold:
                continue
            label_index = int(box.cls[0])
            label = str(names.get(label_index, f"class_{label_index}")).lower().strip()
            detections.append({"label": label, "confidence": round(confidence, 2)})

    return _deduplicate_detections(detections)


def _deduplicate_detections(detections: list[dict]) -> list[dict]:
    """Keep only best confidence per label."""
    best_by_label: dict[str, float] = defaultdict(float)
    for item in detections:
        label = str(item.get("label", "")).strip().lower()
        if not label:
            continue
        conf = float(item.get("confidence", 0.0))
        if conf > best_by_label[label]:
            best_by_label[label] = conf
    merged = [{"label": label, "confidence": round(conf, 2)} for label, conf in best_by_label.items()]
    merged.sort(key=lambda d: (-d["confidence"], d["label"]))
    return merged


def aggregate_burst_detections(per_frame_detections: list[list[dict]]) -> list[dict]:
    """Merge detections across multiple frames and track frame frequency."""
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

    merged = []
    for label, hits in frame_hits.items():
        merged.append(
            {
                "label": label,
                "confidence": round(best_confidence[label], 2),
                "frames_seen": hits,
            }
        )
    merged.sort(key=lambda d: (-d["frames_seen"], -d["confidence"], d["label"]))
    return merged


def build_scene_text(detections: list[dict]) -> str:
    """Build a clean sentence summary for LLM input."""
    if not detections:
        return "I do not detect any clear objects."

    labels = [f"a {item['label']}" for item in detections if item.get("label")]
    if not labels:
        return "I do not detect any clear objects."
    if len(labels) == 1:
        joined = labels[0]
    elif len(labels) == 2:
        joined = f"{labels[0]} and {labels[1]}"
    else:
        joined = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    return f"I detect {joined}."


def build_burst_scene_text(detections: list[dict], total_frames: int) -> str:
    """Build scene summary from detections accumulated over multiple frames."""
    if not detections or total_frames <= 0:
        return "I do not detect any clear objects in the recent frames."

    parts = []
    for item in detections:
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        frames_seen = int(item.get("frames_seen", 0))
        parts.append(f"{label} ({frames_seen}/{total_frames} frames)")

    if not parts:
        return "I do not detect any clear objects in the recent frames."

    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    return f"In the last {total_frames} frames, I detected {joined}."


def get_scene_text(
    camera_index: int = CAMERA_INDEX,
    confidence_threshold: float = CV_CONFIDENCE_THRESHOLD,
    model_path: str = YOLO_MODEL_PATH,
) -> tuple[str, list[dict]]:
    """Capture a frame, detect objects, and return scene text plus detections."""
    frame = capture_frame(camera_index=camera_index)
    detections = detect_objects(
        frame,
        confidence_threshold=confidence_threshold,
        model_path=model_path,
    )
    return build_scene_text(detections), detections


def get_scene_text_burst(
    frame_count: int,
    interval_seconds: float,
    camera_index: int = CAMERA_INDEX,
    confidence_threshold: float = CV_CONFIDENCE_THRESHOLD,
    model_path: str = YOLO_MODEL_PATH,
) -> tuple[str, list[list[dict]], list[dict]]:
    """Capture frame burst, detect objects for each frame, and summarize."""
    frames = capture_frame_burst(
        frame_count=frame_count,
        interval_seconds=interval_seconds,
        camera_index=camera_index,
    )

    per_frame_detections: list[list[dict]] = []
    for frame in frames:
        detections = detect_objects(
            frame,
            confidence_threshold=confidence_threshold,
            model_path=model_path,
        )
        per_frame_detections.append(detections)

    aggregated = aggregate_burst_detections(per_frame_detections)
    scene_text = build_burst_scene_text(aggregated, total_frames=max(len(frames), frame_count))
    return scene_text, per_frame_detections, aggregated
