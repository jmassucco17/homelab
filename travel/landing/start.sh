#!/bin/bash
set -e

cd "$(dirname "$0")"

# Build and start the service
docker compose up --build -d --remove-orphans

echo "Travel landing page started successfully"
