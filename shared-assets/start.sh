#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Building and starting containers..."
sudo docker compose up -d --build --wait