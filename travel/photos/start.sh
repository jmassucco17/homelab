#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Clean up old travel-site container if it exists (migration from old structure)
if sudo docker ps -a --format '{{.Names}}' | grep -q '^travel-site$'; then
  echo "Removing old travel-site container..."
  sudo docker rm -f travel-site 2>/dev/null || true
fi

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Building and starting containers..."
sudo docker compose up -d --build --wait