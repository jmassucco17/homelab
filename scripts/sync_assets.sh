#!/usr/bin/env bash
set -euo pipefail

# Run at repo root (one level up from this directory)
cd "$(dirname "$0")"/..

echo "Syncing shared assets..."

# Define source and destinations
SHARED_DIR="assets"
HOMEPAGE_ASSETS_DIR="homepage/site/assets"
DASHBOARD_ASSETS_DIR="dashboard/app/static"

# Sync files to homepage
echo "Syncing to homepage..."
mkdir -p "${HOMEPAGE_ASSETS_DIR}/icon"
cp -rv "${SHARED_DIR}/icon/" "${HOMEPAGE_ASSETS_DIR}"
mkdir -p "${HOMEPAGE_ASSETS_DIR}/styles/"
cp -v "${SHARED_DIR}"/styles/*.css "${HOMEPAGE_ASSETS_DIR}/styles/"

# Sync files to dashboard
echo "Syncing to dashboard..."
mkdir -p "${DASHBOARD_ASSETS_DIR}/icon"
cp -rv "${SHARED_DIR}/icon/" "${DASHBOARD_ASSETS_DIR}"
mkdir -p "${DASHBOARD_ASSETS_DIR}/styles/"
cp -v "${SHARED_DIR}"/styles/*.css "${DASHBOARD_ASSETS_DIR}/styles/"

echo "✅ Assets synced successfully."