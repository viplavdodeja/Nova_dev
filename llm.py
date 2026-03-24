"""Ollama client for NOVA multimodal testing."""

from __future__ import annotations

import json
from urllib import error, request

from config import OLLAMA_KEEP_ALIVE, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_URL

CHAT_SYSTEM_PROMPT = (
    "You are NOVA, a warm embodied robot assistant. "
    "Reply naturally in 1-2 short sentences that sound good when spoken."
)

MULTIMODAL_SYSTEM_PROMPT = (
    "You are NOVA, a warm embodied robot assistant. "
    "Respond briefly and naturally. "
    "Use scene information only as provided and do not invent unseen objects."
)


def _call_ollama(prompt: str, num_predict: int = 80) -> str:
    """Call Ollama /api/generate with keep_alive and return text or error."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "num_predict": num_predict,
            "temperature": 0.6,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }

    req = request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except error.URLError:
        return (
            f"[LLM ERROR] Could not reach Ollama at {OLLAMA_URL}. "
            "Make sure it is running."
        )
    except TimeoutError:
        return "[LLM ERROR] Ollama request timed out."
    except Exception as exc:
        return f"[LLM ERROR] Request failed: {exc}"

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return "[LLM ERROR] Received malformed JSON from Ollama."

    text = str(data.get("response", "")).strip()
    if not text:
        return "[LLM ERROR] Ollama returned an empty response."
    return text


def warm_llm() -> bool:
    """Preload/warm the model so first user turn has lower latency."""
    prompt = (
        "You are NOVA. Reply with exactly: Ready."
    )
    response = _call_ollama(prompt, num_predict=8)
    if response.startswith("[LLM ERROR]"):
        print(response)
        return False
    print("[LLM] Warmed.")
    return True


def generate_response(user_text: str) -> str:
    """Generate a concise response for plain user text."""
    cleaned = user_text.strip()
    if not cleaned:
        return "[LLM ERROR] Empty user input."

    prompt = (
        f"{CHAT_SYSTEM_PROMPT}\n"
        f"User said: {cleaned}\n"
        "NOVA:"
    )
    return _call_ollama(prompt, num_predict=80)


def generate_multimodal_response(user_text: str, scene_text: str | None) -> str:
    """Generate response from user speech/text and optional scene summary."""
    cleaned_user = user_text.strip()
    if not cleaned_user:
        return "[LLM ERROR] Empty user input."

    cleaned_scene = (scene_text or "Scene unavailable.").strip()
    prompt = (
        f"{MULTIMODAL_SYSTEM_PROMPT}\n"
        f"User said: {cleaned_user}\n"
        f"Current scene: {cleaned_scene}\n"
        "NOVA:"
    )
    return _call_ollama(prompt, num_predict=80)

