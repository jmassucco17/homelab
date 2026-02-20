#!/usr/bin/env bash
# Start a single homelab service by name.
# Handles service-specific logic (networking uses pull instead of build;
# travel/photos includes a one-time container migration step).
#
# Usage: scripts/start_service.sh <service>
# Examples:
#   scripts/start_service.sh networking
#   scripts/start_service.sh blog
#   scripts/start_service.sh travel/photos
set -euo pipefail

SERVICE="${1:?Usage: $0 <service>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR="$REPO_ROOT/$SERVICE"

if [[ ! -d "$SERVICE_DIR" ]]; then
  echo "Error: unknown service '$SERVICE' (directory '$SERVICE_DIR' not found)" >&2
  exit 1
fi

cd "$SERVICE_DIR"

# One-time migration: remove the old travel-site container if it still exists
if [[ "$SERVICE" == "travel/photos" ]]; then
  if sudo docker ps -a --format '{{.Names}}' | grep -q '^travel-site$'; then
    echo "Removing old travel-site container..."
    sudo docker rm -f travel-site 2>/dev/null || true
  fi
fi

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

if [[ "$SERVICE" == "networking" ]]; then
  echo "Pulling latest images..."
  sudo docker compose pull
  echo "Starting up containers..."
  sudo docker compose up -d --wait
else
  echo "Building and starting containers..."
  sudo docker compose up -d --build --wait
fi
