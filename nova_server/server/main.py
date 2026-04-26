"""FastAPI entry point for the isolated NOVA server prototype."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile

from .demo_memory import add_event, get_recent_events
from .frame_utils import ensure_uploads_dir, save_uploaded_frame
from .llm_client import generate_nova_response, is_llm_ready
from .schemas import ReasonRequest, ReasonResponse


load_dotenv()

app = FastAPI(title="nova_server", version="0.1.0")
ensure_uploads_dir()


@app.get("/health")
def health() -> dict[str, object]:
    """Simple health endpoint for demo checks."""
    return {
        "status": "ok",
        "service": "nova_server",
        "llm_ready": is_llm_ready(),
    }


@app.post("/nova/reason", response_model=ReasonResponse)
def reason(request: ReasonRequest) -> ReasonResponse:
    """Reason over Pi-sent JSON context only."""
    add_event(
        {
            "type": "reason",
            "event": request.event,
            "transcript": request.transcript,
            "robot_state": request.robot_state,
        }
    )
    return generate_nova_response(request)


@app.post("/nova/reason-frame", response_model=ReasonResponse)
async def reason_frame(
    context_json: str = Form(...),
    frame: UploadFile | None = File(default=None),
) -> ReasonResponse:
    """Reason over JSON context and an optional uploaded image frame."""
    context_dict = json.loads(context_json)
    request = ReasonRequest.model_validate(context_dict)

    frame_metadata = None
    if frame is not None:
        frame_metadata = await save_uploaded_frame(frame)

    add_event(
        {
            "type": "reason-frame",
            "event": request.event,
            "transcript": request.transcript,
            "robot_state": request.robot_state,
            "frame": frame_metadata,
        }
    )
    return generate_nova_response(request)


@app.get("/memory")
def memory() -> dict[str, object]:
    """Small debug endpoint for demo inspection."""
    return {"recent_events": get_recent_events()}
