#!/usr/bin/env bash
# Start a single homelab service by name.
# If the service directory contains a Dockerfile, images are built locally.
# Otherwise (e.g. networking, which uses pre-built images), images are pulled.
# Pass --staging to use docker-compose.staging.yml instead of docker-compose.yml.
# When staging, images are always pulled (no local build); the image tag is
# controlled by the STAGING_IMAGE_TAG environment variable (default: latest).
#
# Usage: scripts/start_service.sh <service> [--staging]
# Examples:
#   scripts/start_service.sh networking
#   scripts/start_service.sh blog
#   scripts/start_service.sh travel --staging
#   STAGING_IMAGE_TAG=sha-abc1234 scripts/start_service.sh travel --staging
set -euo pipefail

SERVICE="${1:?Usage: $0 <service> [--staging]}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR="$REPO_ROOT/$SERVICE"

STAGING=false
for arg in "${@:2}"; do
  [[ "$arg" == "--staging" ]] && STAGING=true
done

if [[ ! -d "$SERVICE_DIR" ]]; then
  echo "Error: unknown service '$SERVICE' (directory '$SERVICE_DIR' not found)" >&2
  exit 1
fi

cd "$SERVICE_DIR"

# One-time migration: remove old travel sub-containers if they exist (prod only)
if [[ "$SERVICE" == "travel" ]] && [[ "$STAGING" == "false" ]]; then
  for old_container in travel-landing travel-photos travel-maps travel-site; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${old_container}$"; then
      echo "Removing old ${old_container} container..."
      sudo docker rm -f "${old_container}" 2>/dev/null || true
    fi
  done
fi

echo "Shutting down containers..."
if [[ "$STAGING" == "true" ]]; then
  sudo docker compose -f docker-compose.staging.yml down --remove-orphans
else
  sudo docker compose down --remove-orphans
fi

if [[ "$STAGING" == "true" ]]; then
  echo "Pulling and starting staging containers (tag: ${STAGING_IMAGE_TAG:-latest})..."
  sudo STAGING_IMAGE_TAG="${STAGING_IMAGE_TAG:-latest}" docker compose -f docker-compose.staging.yml pull
  sudo STAGING_IMAGE_TAG="${STAGING_IMAGE_TAG:-latest}" docker compose -f docker-compose.staging.yml up -d --wait
elif [[ -f "$SERVICE_DIR/Dockerfile" ]]; then
  echo "Building and starting containers..."
  sudo docker compose up -d --build --wait
else
  echo "Pulling latest images..."
  sudo docker compose pull
  echo "Starting up containers..."
  sudo docker compose up -d --wait
fi
