#!/usr/bin/env bash
# Local development deployment script.
# Starts selected services with a local HTTP-only traefik reverse proxy.
# Skips Cloudflare DDNS (so the real public DNS is never touched) and OAuth.
#
# Usage:
#   ./scripts/start_local.sh                          # Start all services
#   ./scripts/start_local.sh blog                     # Start only blog
#   ./scripts/start_local.sh blog travel/photos        # Start specific services
#   ./scripts/start_local.sh --stop                    # Stop all services
#   ./scripts/start_local.sh blog travel/photos --stop # Stop specific services
#
# Services can be accessed at http://localhost:<port> where <port> can be found
# in the associated docker-compose.local.yml for each service.
#
# Access by hostname (add to /etc/hosts first):
#   127.0.0.1  jamesmassucco.com blog.jamesmassucco.com travel.jamesmassucco.com assets.jamesmassucco.com

set -euo pipefail
cd "$(dirname "$0")"/..

ALL_SERVICES=("shared-assets" "homepage" "blog" "travel" "games" "tools")
LOCAL_HOSTS="jamesmassucco.com blog.jamesmassucco.com travel.jamesmassucco.com assets.jamesmassucco.com games.jamesmassucco.com tools.jamesmassucco.com"

# Parse arguments: extract --stop flag and service names (order-independent)
STOP=false
SERVICES=()
for arg in "$@"; do
  if [[ "$arg" == "--stop" ]]; then
    STOP=true
  else
    SERVICES+=("$arg")
  fi
done

if [ "${#SERVICES[@]}" -eq 0 ]; then
  SERVICES=("${ALL_SERVICES[@]}")
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

if [[ "$STOP" == "true" ]]; then
  # Stop each requested service
  for service in "${SERVICES[@]}"; do
    echo "Stopping $service..."
    pushd "$service" > /dev/null
    sudo docker compose -f docker-compose.yml -f docker-compose.local.yml down --remove-orphans || true
    popd > /dev/null
  done

  # Stop traefik only when stopping all services
  if [ "${#SERVICES[@]}" -eq "${#ALL_SERVICES[@]}" ]; then
    echo "Stopping local networking (traefik)..."
    pushd networking > /dev/null
    sudo docker compose -f docker-compose.local.yml down --remove-orphans || true
    popd > /dev/null
  fi

  echo "Local deployment stopped."
  exit 0
fi

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
  sudo docker compose -f docker-compose.yml -f docker-compose.local.yml pull
  sudo docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --wait
  popd > /dev/null
done

echo ""
echo "Local deployment ready!"
echo ""
echo "Services can be accessed at http://localhost:<port>"
echo "See each service's docker-compose.local.yml for its port mapping."
echo "  traefik dashboard: http://localhost:8080"
echo ""
echo "To access services by hostname, add to /etc/hosts:"
echo "  127.0.0.1  $LOCAL_HOSTS"
