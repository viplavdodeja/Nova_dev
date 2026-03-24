"""Lightweight CV helpers for NOVA scene summaries."""

from __future__ import annotations

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

