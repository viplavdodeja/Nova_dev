#!/usr/bin/env bash
set -euo pipefail

# Run this script from inside the nova_server/ directory.
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
