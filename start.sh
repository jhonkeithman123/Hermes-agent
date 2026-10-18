#!/bin/bash
set -e

# Start keep-alive server in background
python3 /app/server.py &

# Run Hermes Agent
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"