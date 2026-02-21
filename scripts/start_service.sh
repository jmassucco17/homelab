#!/usr/bin/env bash
# Start a single homelab service by name.
# If the service directory contains a Dockerfile, images are built locally.
# Otherwise (e.g. networking, which uses pre-built images), images are pulled.
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

# One-time migration: remove old travel sub-containers if they exist
if [[ "$SERVICE" == "travel" ]]; then
  for old_container in travel-landing travel-photos travel-maps travel-site; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${old_container}$"; then
      echo "Removing old ${old_container} container..."
      sudo docker rm -f "${old_container}" 2>/dev/null || true
    fi
  done
  # One-time migration: remove old volume from previous project name (safe to remove after all envs migrated)
  if sudo docker volume ls --format '{{.Name}}' | grep -q "^travel-site_data-volume$"; then
    echo "Removing old travel-site_data-volume..."
    sudo docker volume rm travel-site_data-volume 2>/dev/null || true
  fi
fi

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

if [[ -f "$SERVICE_DIR/Dockerfile" ]]; then
  echo "Building and starting containers..."
  sudo docker compose up -d --build --wait
else
  echo "Pulling latest images..."
  sudo docker compose pull
  echo "Starting up containers..."
  sudo docker compose up -d --wait
fi
