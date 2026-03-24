"""Local Ollama client for NOVA testing."""

from __future__ import annotations

import json
from urllib import error, request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"
REQUEST_TIMEOUT_SECONDS = 30

CHAT_SYSTEM_PROMPT = (
    "You are Nova, a friendly and witty robot assistant. "
    "Reply naturally in 1-2 short sentences and stay concise."
)

SCENE_SYSTEM_PROMPT = (
    "You are NOVA, an embodied robot assistant. "
    "Respond in one short natural sentence based only on what is in the scene. "
    "Do not invent objects."
)


def _call_ollama(prompt: str, num_predict: int = 60) -> str:
    """Call Ollama generate API and return response text or error marker."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        OLLAMA_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except error.URLError:
        return (
            "[LLM ERROR] Could not reach Ollama at http://localhost:11434. "
            "Make sure Ollama is running."
        )
    except TimeoutError:
        return "[LLM ERROR] Ollama request timed out. Try again."
    except Exception as exc:
        return f"[LLM ERROR] Request failed: {exc}"

    try:
        parsed = json.loads(body)
        text = parsed.get("response", "").strip()
        if not text:
            return "[LLM ERROR] Ollama returned an empty response."
        return text
    except json.JSONDecodeError:
        return "[LLM ERROR] Received malformed JSON from Ollama."


def generate_response(user_text: str) -> str:
    """Send user text to Ollama and return a model response string."""
    cleaned_input = user_text.strip()
    if not cleaned_input:
        return "[LLM ERROR] Please provide a non-empty message."

    prompt = (
        f"{CHAT_SYSTEM_PROMPT}\n"
        f"User message: {cleaned_input}\n"
        "Nova:"
    )
    return _call_ollama(prompt, num_predict=80)


def generate_scene_response(scene_text: str) -> str:
    """Send a scene summary to Ollama and return a scene-grounded response."""
    cleaned_scene = scene_text.strip()
    if not cleaned_scene:
        return "[LLM ERROR] Scene description is empty."

    prompt = (
        f"{SCENE_SYSTEM_PROMPT}\n"
        f"Scene: {cleaned_scene}\n"
        "NOVA:"
    )
    return _call_ollama(prompt, num_predict=50)
