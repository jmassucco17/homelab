#!/usr/bin/env bash
# Start a single homelab service by name, pulling the image from GHCR.
#
# Usage: scripts/start_service.sh <service>
# Examples:
#   scripts/start_service.sh networking
#   scripts/start_service.sh blog
#   scripts/start_service.sh travel
set -euo pipefail

SERVICE="${1:?Usage: $0 <service>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR="$REPO_ROOT/$SERVICE"

if [[ ! -d "$SERVICE_DIR" ]]; then
  echo "Error: unknown service '$SERVICE' (directory '$SERVICE_DIR' not found)" >&2
  exit 1
fi

cd "$SERVICE_DIR"

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Pulling latest images..."
sudo docker compose pull
echo "Starting containers..."
sudo docker compose up -d --wait
