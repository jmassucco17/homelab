#!/usr/bin/env bash
# Start a single homelab service by name, pulling the image from GHCR.
#
# Production (default): merges docker-compose.yml with docker-compose.prod.yml
# (routing labels and bind-mounts), then pulls and starts.
#
# Staging (--staging): merges docker-compose.yml with docker-compose.staging.yml
# under a separate Docker Compose project (staging-<service>) so production
# containers are never affected. The image tag is controlled by the
# STAGING_IMAGE_TAG environment variable (default: latest).
# Services without docker-compose.prod.yml (e.g. networking) use only their
# docker-compose.staging.yml as a standalone file.
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

if [[ "$STAGING" == "true" ]]; then
  PROJ="staging-${SERVICE}"
  if [[ -f "docker-compose.prod.yml" ]]; then
    # Overlay: base + staging (no prod labels; isolated by project name)
    COMPOSE="-p ${PROJ} -f docker-compose.yml -f docker-compose.staging.yml"
  else
    # Standalone staging file (e.g. networking)
    COMPOSE="-p ${PROJ} -f docker-compose.staging.yml"
  fi

  echo "Shutting down staging containers..."
  sudo docker compose ${COMPOSE} down --remove-orphans

  echo "Pulling and starting staging containers (tag: ${STAGING_IMAGE_TAG:-latest})..."
  sudo STAGING_IMAGE_TAG="${STAGING_IMAGE_TAG:-latest}" docker compose ${COMPOSE} pull
  sudo STAGING_IMAGE_TAG="${STAGING_IMAGE_TAG:-latest}" docker compose ${COMPOSE} up -d --wait
else
  if [[ -f "docker-compose.prod.yml" ]]; then
    COMPOSE="-f docker-compose.yml -f docker-compose.prod.yml"
  else
    COMPOSE="-f docker-compose.yml"
  fi

  echo "Shutting down containers..."
  sudo docker compose ${COMPOSE} down --remove-orphans

  echo "Pulling latest images..."
  sudo docker compose ${COMPOSE} pull
  echo "Starting containers..."
  sudo docker compose ${COMPOSE} up -d --wait
fi
