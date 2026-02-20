#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Clean up old travel containers if they exist (migration from 3-container structure)
for old_container in travel-landing travel-photos travel-maps; do
  if sudo docker ps -a --format '{{.Names}}' | grep -q "^${old_container}$"; then
    echo "Removing old ${old_container} container..."
    sudo docker rm -f "${old_container}" 2>/dev/null || true
  fi
done

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Building and starting containers..."
sudo docker compose up -d --build --wait
