#!/usr/bin/env bash
cd "$(dirname "$0")"/..

PROJECTS=("networking" "monitoring" "homepage" "dashboard")

for project in "${PROJECTS[@]}"; do
  echo "Starting $project..."
  pushd "$project" > /dev/null
  ./start.sh
  popd > /dev/null
done