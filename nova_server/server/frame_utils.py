"""Helpers for saving uploaded frames for the NOVA server."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import UploadFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOADS_DIR = PROJECT_ROOT / "uploads"


def ensure_uploads_dir() -> Path:
    """Create the uploads directory if it does not exist."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOADS_DIR


def build_timestamped_filename(original_name: str | None) -> str:
    """Build a timestamped filename while preserving the original suffix when possible."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    suffix = Path(original_name or "frame.bin").suffix or ".bin"
    return f"frame_{timestamp}{suffix}"


async def save_uploaded_frame(upload_file: UploadFile) -> dict[str, str | int]:
    """Save an uploaded frame file and return simple metadata."""
    uploads_dir = ensure_uploads_dir()
    filename = build_timestamped_filename(upload_file.filename)
    target_path = uploads_dir / filename

    content = await upload_file.read()
    target_path.write_bytes(content)

    return {
        "filename": filename,
        "size_bytes": len(content),
    }
