"""LLM service wrapper for intent interpretation and responses."""

from __future__ import annotations


class LLMService:
    """Structured action planner for coordinator-driven execution."""

    def plan_from_command(self, transcript: str) -> dict:
        """Return a minimal structured action plan for a command transcript."""
        normalized = transcript.strip().lower()
        if not normalized:
            return {"type": "noop"}

        if "look left" in normalized:
            return {"type": "servo", "action": "look_left"}
        if "look right" in normalized:
            return {"type": "servo", "action": "look_right"}
        if "forward" in normalized:
            return {"type": "motion", "action": "forward"}
        if "backward" in normalized or "reverse" in normalized:
            return {"type": "motion", "action": "backward"}
        if "turn left" in normalized:
            return {"type": "motion", "action": "turn_left"}
        if "turn right" in normalized:
            return {"type": "motion", "action": "turn_right"}

        return {"type": "speak", "text": "I heard you, but I do not have an action for that yet."}
