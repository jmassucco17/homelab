#!/usr/bin/env bash
set -euo pipefail

# Start a service using docker compose
# Usage: ./scripts/start_service.sh <service_path>
# Example: ./scripts/start_service.sh blog

if [ $# -eq 0 ]; then
  echo "Usage: $0 <service_path>" >&2
  echo "Example: $0 blog" >&2
  echo "Example: $0 travel/maps" >&2
  exit 1
fi

SERVICE_PATH="$1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$REPO_ROOT/$SERVICE_PATH" ]; then
  echo "Error: Service directory '$SERVICE_PATH' does not exist" >&2
  exit 1
fi

cd "$REPO_ROOT/$SERVICE_PATH"

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Building and starting containers..."
sudo docker compose up -d --build --wait
