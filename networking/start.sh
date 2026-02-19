#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Pulling latest images..."
sudo docker compose pull

echo "Starting up containers..."
sudo docker compose up -d --wait