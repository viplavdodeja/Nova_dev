#!/usr/bin/env bash
set -euo pipefail

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
