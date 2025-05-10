#!/usr/bin/env bash

# Run at repo root (one level up from this directory)
cd "$(dirname "$0")"/..

PROJECTS=("networking" "monitoring" "homepage" "dashboard")

for project in "${PROJECTS[@]}"; do
  echo "Starting $project..."
  pushd "$project" > /dev/null
  ./start.sh
  popd > /dev/null
done