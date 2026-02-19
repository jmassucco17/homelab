#!/usr/bin/env bash
# Script to migrate the database by recreating it with the new schema

echo "Backing up old database..."
docker exec travel-photos cp /data/travel.db /data/travel.db.backup 2>/dev/null || echo "No existing database to backup"

echo "Removing old database..."
docker exec travel-photos rm /data/travel.db 2>/dev/null || echo "No database to remove"

echo "Database removed. It will be recreated on next request with the new schema."
echo "Old data backed up to /data/travel.db.backup in the container"
