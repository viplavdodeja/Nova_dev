"""Simple Pi-side client for the NOVA server prototype."""

from __future__ import annotations

import json
from pathlib import Path

import requests


DEFAULT_TIMEOUT_SECONDS = 5
FALLBACK_RESPONSE = {
    "reply": "Server reasoning is unavailable, continuing local demo mode.",
    "intent": "speak_only",
    "suggested_action": "none",
    "safety_note": "fallback from Pi client",
}


def check_server_health(server_url: str) -> bool:
    """Return True if the NOVA server health endpoint responds successfully."""
    health_url = server_url.rstrip("/") + "/health"
    try:
        response = requests.get(health_url, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
    except Exception:
        return False

    try:
        data = response.json()
    except Exception:
        return False

    return data.get("status") == "ok"


def ask_nova_server(server_url: str, payload: dict) -> dict:
    """Send a JSON reasoning request and fail safely if the server is unavailable."""
    reason_url = server_url.rstrip("/") + "/nova/reason"
    try:
        response = requests.post(reason_url, json=payload, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except Exception:
        return dict(FALLBACK_RESPONSE)


def ask_nova_server_with_frame(server_url: str, payload: dict, frame_path: str | None) -> dict:
    """Send a reasoning request with an optional frame file and fail safely."""
    reason_url = server_url.rstrip("/") + "/nova/reason-frame"
    files = None

    try:
        if frame_path:
            path = Path(frame_path)
            if path.exists():
                files = {"frame": (path.name, path.read_bytes(), "application/octet-stream")}

        response = requests.post(
            reason_url,
            data={"context_json": json.dumps(payload)},
            files=files,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return dict(FALLBACK_RESPONSE)
