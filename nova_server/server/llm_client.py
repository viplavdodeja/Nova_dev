"""Minimal LLM wrapper with OpenAI-first reasoning and deterministic fallback behavior."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from .schemas import ReasonRequest, ReasonResponse


DEFAULT_SAFETY_NOTE = "movement handled locally by Pi"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_NOVA_SYSTEM_PROMPT = (
    "You are NOVA, a witty but professional AI robot being used in a live tech demo. "
    "Sound friendly, confident, and slightly playful without becoming cheesy. "
    "Keep replies short enough to speak aloud comfortably. "
    "When useful, mention what you detect in the scene or how close someone is. "
    "Never output raw robot motor commands. "
    "Never suggest unsafe movement. "
    "The Raspberry Pi handles all movement, safety, and Arduino control locally."
)


def _build_scene_summary(request: ReasonRequest) -> str:
    """Create a short scene summary from detections."""
    if not request.detections:
        return "I do not see a person clearly right now."

    parts: list[str] = []
    for detection in request.detections[:3]:
        parts.append(
            f"{detection.label} at {detection.position} "
            f"with confidence {detection.confidence:.2f}"
        )
    return "I currently see " + ", ".join(parts) + "."


def _fallback_response(request: ReasonRequest) -> ReasonResponse:
    """Rule-based response path used when no live LLM is available."""
    if request.distance_inches is not None and request.distance_inches < 18:
        return ReasonResponse(
            reply="I am close to someone, so I will stay still for safety.",
            intent="stop_for_safety",
            suggested_action="stop",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    if not request.detections:
        return ReasonResponse(
            reply="I do not see a person clearly right now, so I will stay still.",
            intent="describe_scene",
            suggested_action="none",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    if request.event == "good_morning":
        person_count = sum(1 for detection in request.detections if detection.label.lower() == "person")
        if person_count > 0:
            reply = "Good morning. I see someone in front of me and I am ready for the demo."
        else:
            reply = "Good morning. I am ready and I am checking the scene now."
        return ReasonResponse(
            reply=reply,
            intent="greet_user",
            suggested_action="speak",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    return ReasonResponse(
        reply=f"{_build_scene_summary(request)} Movement and safety remain local.",
        intent="speak_only",
        suggested_action="none",
        safety_note=DEFAULT_SAFETY_NOTE,
    )


def _build_prompt(request: ReasonRequest) -> str:
    """Build a short prompt for a local LLM endpoint."""
    system_prompt = os.getenv("NOVA_SYSTEM_PROMPT", DEFAULT_NOVA_SYSTEM_PROMPT).strip()
    request_json = json.dumps(request.model_dump(), indent=2)
    return (
        f"{system_prompt}\n\n"
        "Return only a short spoken reply for the demo.\n"
        "Keep it natural and expressive, but concise.\n"
        "Do not output JSON.\n"
        "Do not output raw robot motor commands.\n"
        "Do not suggest unsafe movement.\n"
        "Movement and safety remain local to the Raspberry Pi.\n\n"
        f"Context:\n{request_json}\n\n"
        "Write one concise spoken reply."
    )


def is_llm_ready() -> bool:
    """Return whether an external LLM is configured."""
    if os.getenv("OPENAI_API_KEY", "").strip():
        return True
    if os.getenv("OLLAMA_URL", "").strip() and os.getenv("OLLAMA_MODEL", "").strip():
        return True
    return False


def _extract_openai_text(data: dict[str, Any]) -> str:
    """Extract assistant text from a Responses API result."""
    output_items = data.get("output", [])
    parts: list[str] = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = str(content.get("text", "")).strip()
                if text:
                    parts.append(text)
    return " ".join(parts).strip()


def _try_openai_reasoning(request: ReasonRequest) -> ReasonResponse | None:
    """Try to get a short reply from OpenAI Responses API."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "input": _build_prompt(request),
        "max_output_tokens": 120,
        "text": {"format": {"type": "text"}},
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers=headers,
            json=payload,
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    reply = _extract_openai_text(data)
    if not reply:
        return None

    if request.distance_inches is not None and request.distance_inches < 18:
        return ReasonResponse(
            reply=reply,
            intent="stop_for_safety",
            suggested_action="stop",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    if request.event == "good_morning":
        return ReasonResponse(
            reply=reply,
            intent="greet_user",
            suggested_action="speak",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    if not request.detections:
        return ReasonResponse(
            reply=reply,
            intent="describe_scene",
            suggested_action="none",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    return ReasonResponse(
        reply=reply,
        intent="speak_only",
        suggested_action="none",
        safety_note=DEFAULT_SAFETY_NOTE,
    )


def _try_ollama_reasoning(request: ReasonRequest) -> ReasonResponse | None:
    """Try to get a short reply from Ollama, then wrap it in a safe response schema."""
    ollama_url = os.getenv("OLLAMA_URL", "").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()
    if not ollama_url or not ollama_model:
        return None

    payload: dict[str, Any] = {
        "model": ollama_model,
        "prompt": _build_prompt(request),
        "stream": False,
    }

    try:
        response = requests.post(ollama_url, json=payload, timeout=8)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    reply = str(data.get("response", "")).strip()
    if not reply:
        return None

    if request.distance_inches is not None and request.distance_inches < 18:
        return ReasonResponse(
            reply=reply,
            intent="stop_for_safety",
            suggested_action="stop",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    if request.event == "good_morning":
        return ReasonResponse(
            reply=reply,
            intent="greet_user",
            suggested_action="speak",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    if not request.detections:
        return ReasonResponse(
            reply=reply,
            intent="describe_scene",
            suggested_action="none",
            safety_note=DEFAULT_SAFETY_NOTE,
        )

    return ReasonResponse(
        reply=reply,
        intent="speak_only",
        suggested_action="none",
        safety_note=DEFAULT_SAFETY_NOTE,
    )


def generate_nova_response(request: ReasonRequest) -> ReasonResponse:
    """Generate a safe, short NOVA response using OpenAI, Ollama, or a local fallback."""
    llm_response = _try_openai_reasoning(request)
    if llm_response is not None:
        return llm_response

    llm_response = _try_ollama_reasoning(request)
    if llm_response is not None:
        return llm_response
    return _fallback_response(request)
