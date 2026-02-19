#!/usr/bin/env bash

# Run at repo root (one level up from this directory)
cd "$(dirname "$0")"/..

PROJECTS=("networking" "shared-assets" "homepage" "blog" "travel-site" "travel-maps")

for project in "${PROJECTS[@]}"; do
  echo "Starting $project..."
  pushd "$project" > /dev/null
  ./start.sh
  popd > /dev/null
done