NOVA Server Prototype

This directory adds an isolated IBM/Linux server reasoning layer for Project NOVA.

What this does
- Provides a small FastAPI service for higher-level reasoning.
- Accepts Pi-sent context such as transcript, detections, distance, and robot state.
- Returns short, safe, high-level intents and replies.
- Optionally accepts an uploaded frame for future scene-aware reasoning.

What this does not do
- It does not replace existing Pi logic.
- It does not control Arduino motors directly.
- It does not issue raw movement commands like `F1000`, `R300`, or `SV90`.
- It is not responsible for emergency stop timing.

How this fits the NOVA architecture
- Raspberry Pi remains responsible for:
  - wake phrase
  - STT
  - command parsing
  - YOLO/person detection
  - servo tracking
  - ultrasonic reads
  - local speech output
  - Arduino serial commands
- Arduino remains responsible for:
  - motor commands
  - servo commands
  - LED status
  - ultrasonic `DIST` response
- This server is responsible for:
  - higher-level LLM text response
  - scene/context reasoning from Pi-sent data
  - optional frame upload handling
  - a persistent reasoning process that stays warm for the demo

LLM provider order
- OpenAI is the primary provider when `OPENAI_API_KEY` is configured.
- Default OpenAI model for this prototype: `gpt-4.1-mini`
- Ollama remains available as a secondary option if OpenAI is not configured.
- If both are unavailable, the server falls back to deterministic rule-based responses.

Setup

1. Create and activate a virtual environment.

```bash
cd nova_server
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Copy the environment template if you want custom settings.

```bash
cp .env.example .env
```

4. Put your OpenAI API key in `.env` on the server.

Example:

```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Run the server locally

From inside the `nova_server/` directory:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

Or use the helper script:

```bash
./scripts/run_server.sh
```

Test `/health`

```bash
curl http://127.0.0.1:8080/health
```

Test `/nova/reason`

```bash
curl -X POST http://127.0.0.1:8080/nova/reason \
  -H "Content-Type: application/json" \
  -d '{
    "event": "good_morning",
    "transcript": "good morning nova",
    "detections": [
      {
        "label": "person",
        "confidence": 0.94,
        "position": "center"
      }
    ],
    "distance_inches": 28,
    "robot_state": "idle"
  }'
```

Or use the helper script:

```bash
./scripts/test_reason.sh
```

Test the Python client

From inside `nova_server/`:

```bash
python -m client.test_client --server-url http://127.0.0.1:8080
```

Pi-side client usage later

The Pi client module is in:
- `nova_server/client/nova_server_client.py`

It is intended to be imported later from existing Pi code without changing the overall NOVA architecture.

Future integration example

This is only a future note. Existing demo scripts are not modified by this prototype.

```python
from nova_server.client.nova_server_client import ask_nova_server

payload = {
    "event": "good_morning",
    "transcript": "good morning nova",
    "detections": detections,
    "distance_inches": distance,
    "robot_state": "idle",
}

response = ask_nova_server("http://IBM_SERVER_IP:8080", payload)
speak(response["reply"])
```

Recommended demo flow

1. Pi hears `good morning`.
2. Pi runs local greeting motion.
3. Pi captures detections and ultrasonic distance.
4. Pi sends context to the IBM/Linux server.
5. Server returns a short high-level response.
6. Pi speaks the response locally.
7. Pi keeps all movement and safety local.

Safety note

The server returns only high-level intents and suggested actions. The Pi remains the authority for:
- safety checks
- emergency stop behavior
- distance enforcement
- Arduino serial control
