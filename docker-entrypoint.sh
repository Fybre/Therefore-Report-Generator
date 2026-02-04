#!/bin/bash
set -e

# Ensure data directories are owned by appuser (for volume mounts)
if [ "$1" = "uvicorn" ]; then
    chown -R appuser:appuser /app/data /app/email_templates 2>/dev/null || true
    exec gosu appuser "$@"
fi

exec "$@"
