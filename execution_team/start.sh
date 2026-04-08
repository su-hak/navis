#!/bin/bash
# Execution Team FastAPI Server Startup Script

# Exit on error
set -e

echo "Starting Execution Team API Server..."

# Run uvicorn with FastAPI app
exec uvicorn api:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 1 \
    --log-level info
