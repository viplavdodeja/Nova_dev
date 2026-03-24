"""Vision helpers for NOVA CV scene testing."""

from __future__ import annotations

from collections import defaultdict

try:
    import cv2
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - environment dependent
    YOLO = None

_MODEL = None


def _get_model(model_path: str = "yolo11n.pt"):
    """Load and cache YOLO model."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if YOLO is None:
        raise RuntimeError("ultralytics is not installed.")
    _MODEL = YOLO(model_path)
    return _MODEL


def capture_frame(camera_index: int = 0):
    """Capture one frame from a webcam and return image data or None."""
    if cv2 is None:
        raise RuntimeError("opencv-python is not installed.")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        return None

    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return frame


def detect_objects(frame, confidence_threshold: float = 0.5, model_path: str = "yolo11n.pt") -> list[dict]:
    """Run YOLO detection and return cleaned detection dictionaries."""
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

    return deduplicate_detections(detections)


def deduplicate_detections(detections: list[dict]) -> list[dict]:
    """Keep the highest-confidence detection per label."""
    best_by_label: dict[str, float] = defaultdict(float)
    for item in detections:
        label = str(item.get("label", "")).strip().lower()
        if not label:
            continue
        confidence = float(item.get("confidence", 0.0))
        if confidence > best_by_label[label]:
            best_by_label[label] = confidence

    merged = [{"label": label, "confidence": round(conf, 2)} for label, conf in best_by_label.items()]
    merged.sort(key=lambda d: (-d["confidence"], d["label"]))
    return merged


def build_scene_text(detections: list[dict]) -> str:
    """Convert detection list into a concise human-readable scene sentence."""
    if not detections:
        return "I do not detect any clear objects."

    labels = [d["label"] for d in detections if d.get("label")]
    phrases = [f"a {label}" for label in labels]

    if len(phrases) == 1:
        joined = phrases[0]
    elif len(phrases) == 2:
        joined = f"{phrases[0]} and {phrases[1]}"
    else:
        joined = ", ".join(phrases[:-1]) + f", and {phrases[-1]}"

    return f"I detect {joined}."

