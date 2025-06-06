#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down

echo "Updating container images..."
sudo docker compose build dashboard

echo "Starting up containers..."
sudo docker compose up -d