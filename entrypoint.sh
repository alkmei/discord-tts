#!/bin/sh
# Fix permissions of the shared folder at runtime
chown -R appuser:appuser /app/shared
# Hand off to the CMD
exec "$@"