#!/usr/bin/env bash
set -euo pipefail

# Run at repo root (one level up from this directory)
cd "$(dirname "$0")"/..

echo "Syncing shared assets..."

SHARED_DIR="shared-assets"
SYNCED_DIRS=("homepage/site/assets" "blog/site/assets" "dashboard/app/assets" "mortgage-calc/app/assets")

for synced_dir in "${SYNCED_DIRS[@]}"; do
    echo "Syncing to $synced_dir..."
    # Ensure directories exist
    mkdir -p "${synced_dir}/icon"
    mkdir -p "${synced_dir}/scripts"
    mkdir -p "${synced_dir}/styles"

    # Copy entire icon directory (we don't expect any custom per-container icons)
    cp -rv "${SHARED_DIR}/icon/" "${synced_dir}"
    # Copy script and style files without overwriting other files in target directories
    cp -v "${SHARED_DIR}"/scripts/*.js "${synced_dir}/scripts/"
    cp -v "${SHARED_DIR}"/styles/*.css "${synced_dir}/styles/"
done


echo "✅ Assets synced successfully."