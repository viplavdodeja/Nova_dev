"""Pydantic request and response schemas for the NOVA server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


IntentType = Literal[
    "speak_only",
    "greet_user",
    "describe_scene",
    "suggest_follow",
    "stop_for_safety",
    "no_action",
]

SuggestedActionType = Literal[
    "none",
    "speak",
    "stop",
    "look_left",
    "look_right",
    "look_center",
]


class Detection(BaseModel):
    """A simplified detection record sent from the Pi."""

    label: str = Field(..., description="Detected object label, such as person.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence from 0 to 1.")
    position: str = Field(..., description="Approximate position in frame, such as left, center, or right.")


class ReasonRequest(BaseModel):
    """Reasoning request sent from the Pi to the server."""

    event: str = Field(..., description="High-level event name such as good_morning.")
    transcript: str = Field(..., description="Recognized user speech or command transcript.")
    detections: list[Detection] = Field(default_factory=list, description="Simplified detections from Pi-side CV.")
    distance_inches: float | None = Field(
        default=None,
        description="Ultrasonic distance reading in inches from the Pi-side robot.",
    )
    robot_state: str = Field(..., description="Current local robot state from the Pi.")


class ReasonResponse(BaseModel):
    """High-level server response. No raw motor commands are allowed."""

    reply: str = Field(..., description="Short, natural response for the Pi to speak locally.")
    intent: IntentType = Field(..., description="High-level reasoning intent.")
    suggested_action: SuggestedActionType = Field(..., description="High-level safe suggestion only.")
    safety_note: str = Field(..., description="Reminder that movement and safety remain local to the Pi.")
