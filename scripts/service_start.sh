#!/usr/bin/env bash
# Shared service start helper.
# Call this from a service directory's start.sh to bring down the old containers
# and rebuild / restart with docker compose.
#
# Usage (from the service's own start.sh):
#   REPO_ROOT="$(dirname "$0")/.."   # adjust depth as needed
#   source "$REPO_ROOT/scripts/service_start.sh"
set -euo pipefail

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Building and starting containers..."
sudo docker compose up -d --build --wait
