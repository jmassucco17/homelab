#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down

echo "Updating container images..."
sudo docker compose build travel-admin
sudo docker compose build travel-public

echo "Starting up containers..."
sudo docker compose up -d