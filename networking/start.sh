#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down

echo "Updating container images..."
sudo docker compose pull

echo "Updating Cloudflare allowed IPs..."
./update_cloudflare.sh

echo "Starting up containers..."
sudo docker compose up -d