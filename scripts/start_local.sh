#!/usr/bin/env bash
# Local development deployment script.
# Starts selected services with a local HTTP-only traefik reverse proxy.
# Skips Cloudflare DDNS (so the real public DNS is never touched) and OAuth.
#
# Usage:
#   ./scripts/start_local.sh                          # Start all services
#   ./scripts/start_local.sh blog                     # Start only blog
#   ./scripts/start_local.sh blog travel-site         # Start specific services
#
# Direct port access (no /etc/hosts needed):
#   http://localhost:8001  — homepage
#   http://localhost:8002  — blog
#   http://localhost:8000  — travel-site
#   http://localhost:8003  — shared-assets
#   http://localhost:8080  — traefik dashboard
#
# Access by hostname (add to /etc/hosts first):
#   127.0.0.1  jamesmassucco.com blog.jamesmassucco.com travel.jamesmassucco.com assets.jamesmassucco.com

set -euo pipefail
cd "$(dirname "$0")"/..

ALL_SERVICES=("shared-assets" "homepage" "blog" "travel-site")
LOCAL_HOSTS="jamesmassucco.com blog.jamesmassucco.com travel.jamesmassucco.com assets.jamesmassucco.com"

if [ $# -eq 0 ]; then
  SERVICES=("${ALL_SERVICES[@]}")
else
  SERVICES=("$@")
fi

# Validate provided service names
for service in "${SERVICES[@]}"; do
  valid=false
  for known in "${ALL_SERVICES[@]}"; do
    [[ "$service" == "$known" ]] && valid=true && break
  done
  if [[ "$valid" == "false" ]]; then
    echo "Unknown service: '$service'. Available services: ${ALL_SERVICES[*]}" >&2
    exit 1
  fi
done

# Ensure the shared docker network exists
if ! sudo docker network inspect web >/dev/null 2>&1; then
  echo "Creating docker network 'web'..."
  sudo docker network create web
fi

# Start local traefik (HTTP only, no Cloudflare DDNS or OAuth)
echo "Starting local networking (traefik)..."
pushd networking > /dev/null
sudo docker compose -f docker-compose.local.yml up -d --wait
popd > /dev/null

# Start each requested service with its local overrides
for service in "${SERVICES[@]}"; do
  echo "Starting $service..."
  pushd "$service" > /dev/null
  sudo docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build --wait
  popd > /dev/null
done

echo ""
echo "Local deployment ready!"
echo ""
echo "Direct port access:"
for service in "${SERVICES[@]}"; do
  case $service in
    homepage)      echo "  homepage:      http://localhost:8001" ;;
    blog)          echo "  blog:          http://localhost:8002" ;;
    travel-site)   echo "  travel-site:   http://localhost:8000" ;;
    shared-assets) echo "  shared-assets: http://localhost:8003" ;;
  esac
done
echo "  traefik dashboard: http://localhost:8080"
echo ""
echo "To access services by hostname, add to /etc/hosts:"
echo "  127.0.0.1  $LOCAL_HOSTS"
