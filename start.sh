#!/bin/bash
set -e

# Configure Hermes to use Gemini if GOOGLE_API_KEY is present
if [ -n "$GOOGLE_API_KEY" ]; then
    hermes config set model.provider gemini 2>/dev/null || true
    hermes config set model.default gemini-2.5-flash 2>/dev/null || true
    hermes config set auxiliary.title_generation.provider gemini 2>/dev/null || true
    hermes config set auxiliary.title_generation.model gemini-2.5-flash 2>/dev/null || true
fi

# Start keep-alive server in background
python3 /app/server.py &


# Run Hermes Agent
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"