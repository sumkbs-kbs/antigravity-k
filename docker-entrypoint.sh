#!/bin/bash
# Antigravity-K Docker Entrypoint
set -e

# If AGK_ACCESS_PIN is set, export it for the application
if [ -n "$AGK_ACCESS_PIN" ]; then
    export AGK_ACCESS_PIN
fi

# If AGK_CORS_ORIGINS is set, export it
if [ -n "$AGK_CORS_ORIGINS" ]; then
    export AGK_CORS_ORIGINS
fi

echo "Starting Antigravity-K server..."
exec "$@"
