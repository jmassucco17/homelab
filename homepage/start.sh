#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down

echo "Generating blog HTML..."
../venv/bin/python3 ./generate_blog.py

echo "Updating container images..."
sudo docker compose build homepage

echo "Starting up containers..."
sudo docker compose up -d