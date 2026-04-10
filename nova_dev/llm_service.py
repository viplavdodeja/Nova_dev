"""LLM service wrapper for intent interpretation and responses."""

from __future__ import annotations

import json
import re
from urllib import error, request

from config import RuntimeConfig


DURATION_REGEX = re.compile(
    r"\bfor\s+(?P<value>(?:\d+(?:\.\d+)?)|(?:an?|half|one|two|three|four|five|six|seven|eight|nine|ten))\s+"
    r"(?P<unit>second|seconds|sec|secs|millisecond|milliseconds|ms)\b"
)
NUMBER_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "half": 0.5,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}

COMMAND_PATTERNS = [
    ("look left", ("servo_named", "look_left", None)),
    ("look right", ("servo_named", "look_right", None)),
    ("look forward", ("servo_named", "look_center", None)),
    ("center camera", ("servo_named", "look_center", None)),
    ("center view", ("servo_named", "look_center", None)),
    ("u turn left", ("motion", "u_turn_left", None)),
    ("u-turn left", ("motion", "u_turn_left", None)),
    ("u turn right", ("motion", "u_turn_right", None)),
    ("u-turn right", ("motion", "u_turn_right", None)),
    ("u turn", ("motion", "u_turn_right", None)),
    ("u-turn", ("motion", "u_turn_right", None)),
    ("spin left", ("motion", "spin_left", None)),
    ("spin right", ("motion", "spin_right", None)),
    ("turn left", ("motion", "turn_left", None)),
    ("left turn", ("motion", "turn_left", None)),
    ("turn right", ("motion", "turn_right", None)),
    ("right turn", ("motion", "turn_right", None)),
    ("move forward", ("motion", "forward", None)),
    ("go forward", ("motion", "forward", None)),
    ("forward", ("motion", "forward", None)),
    ("move backward", ("motion", "backward", None)),
    ("go backward", ("motion", "backward", None)),
    ("backward", ("motion", "backward", None)),
    ("reverse", ("motion", "backward", None)),
    ("back", ("motion", "backward", None)),
    ("stop", ("motion", "stop", None)),
]


class LLMService:
    """Structured action planner and speech generator for Nova."""

    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config

    def warm(self) -> bool:
        response = self._call_ollama("You are NOVA. Reply with exactly: Ready.", num_predict=8)
        if response.startswith("[LLM ERROR]"):
            print(response)
            return False
        print("[LLM] Warmed.")
        return True

    def plan_from_command(self, transcript: str, scene_text: str | None = None) -> dict:
        normalized = self._normalize_text(transcript)
        if not normalized:
            return {"type": "noop"}

        for phrase, (plan_type, action, _) in COMMAND_PATTERNS:
            if phrase in normalized:
                duration_ms = self._parse_duration_ms(normalized)
                return {"type": plan_type, "action": action, "duration_ms": duration_ms}

        reply = self.generate_multimodal_response(normalized, scene_text)
        return {"type": "speak", "text": reply}

    def generate_multimodal_response(self, user_text: str, scene_text: str | None) -> str:
        prompt = (
            "You are NOVA, a warm embodied robot assistant. "
            "Respond briefly and naturally. "
            "Use scene information only as provided and do not invent unseen objects.\n"
            f"User said: {user_text.strip()}\n"
            f"Current scene: {(scene_text or 'Scene unavailable.').strip()}\n"
            "NOVA:"
        )
        return self._call_ollama(prompt, num_predict=80)

    def _call_ollama(self, prompt: str, num_predict: int = 80) -> str:
        payload = {
            "model": self._config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self._config.ollama_keep_alive,
            "options": {
                "num_predict": num_predict,
                "temperature": 0.6,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }
        req = request.Request(
            self._config.ollama_url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self._config.ollama_timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.URLError:
            return f"[LLM ERROR] Could not reach Ollama at {self._config.ollama_url}."
        except TimeoutError:
            return "[LLM ERROR] Ollama request timed out."
        except Exception as exc:
            return f"[LLM ERROR] Request failed: {exc}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return "[LLM ERROR] Received malformed JSON from Ollama."
        text = str(data.get("response", "")).strip()
        return text or "[LLM ERROR] Ollama returned an empty response."

    @staticmethod
    def _normalize_text(text: str) -> str:
        lowered = (text or "").strip().lower()
        return re.sub(r"\s+", " ", lowered)

    @staticmethod
    def _parse_duration_ms(text: str) -> int | None:
        match = DURATION_REGEX.search(text)
        if match is None:
            return None
        raw_value = match.group("value")
        raw_unit = match.group("unit")
        try:
            numeric_value = float(raw_value)
        except ValueError:
            numeric_value = NUMBER_WORDS.get(raw_value)
        if numeric_value is None or numeric_value <= 0:
            return None
        if raw_unit.startswith("ms") or raw_unit.startswith("millisecond"):
            return int(numeric_value)
        return int(numeric_value * 1000)
