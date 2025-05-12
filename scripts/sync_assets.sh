#!/usr/bin/env bash
set -euo pipefail

# Run at repo root (one level up from this directory)
cd "$(dirname "$0")"/..

echo "Syncing shared assets..."

SHARED_DIR="shared-assets"
SYNCED_DIRS=("homepage/site/assets" "blog/site/assets" "dashboard/app/assets")

for synced_dir in "${SYNCED_DIRS[@]}"; do
    echo "Syncing to $synced_dir..."
    mkdir -p "${synced_dir}/icon"
    cp -rv "${SHARED_DIR}/icon/" "${synced_dir}"
    mkdir -p "${synced_dir}/styles/"
    cp -v "${SHARED_DIR}"/styles/*.css "${synced_dir}/styles/"
done


echo "✅ Assets synced successfully."