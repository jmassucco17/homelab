# Deployment Guide

This document describes every way to deploy the homelab services, how they relate to each
other, and when to use each one.

---

## Overview

All four deployment modes share a common runtime: **`scripts/start_service.sh`**.
The script starts a single service by name, choosing the right Compose file(s) based on
the mode. The modes differ only in *which* Compose file is used and *where* the script runs.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        scripts/start_service.sh                        │
│                                                                        │
│  No flags        → docker-compose.yml          (production image)      │
│  --staging       → docker-compose.staging.yml  (staging image)         │
└────────────────────────────────────────────────────────────────────────┘
         ▲                    ▲                       ▲
         │                    │                       │
   CI integration       Production deploy       Staging deploy
   (docker-integration  (.github/workflows/     (.github/workflows/
    .yml via             deploy.yml)             deploy-staging.yml)
    start-service
    action)
```

Local development uses a separate script (`scripts/start_local.sh`) because it starts an
HTTP-only Traefik instance with no TLS or OAuth, which is fundamentally different from the
production networking setup.

---

## 1. Local Development

**Script:** `scripts/start_local.sh`  
**Compose files used:** `docker-compose.yml` + `docker-compose.local.yml` (per service) and
`networking/docker-compose.local.yml` (HTTP-only Traefik)

### Purpose

Spin up services on a local machine for active development. No TLS, no OAuth, no
Cloudflare — services are reachable at `http://localhost:<port>` or by hostname via
`/etc/hosts`.

### Usage

```bash
# Start all services
./scripts/start_local.sh

# Start specific services
./scripts/start_local.sh blog travel

# Stop all services
./scripts/start_local.sh --stop

# Stop specific services
./scripts/start_local.sh blog --stop
```

### How it works

1. Creates the `web` Docker network if it doesn't exist.
2. Starts an HTTP-only Traefik instance from `networking/docker-compose.local.yml`.
3. For each requested service, starts containers with
   `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build --wait`.
4. The `docker-compose.local.yml` override maps a host port and sets the Traefik router
   to use the `web` entrypoint (HTTP) instead of `websecure` (HTTPS).

### Accessing services

Each service's `docker-compose.local.yml` maps a specific host port. Add the following to
`/etc/hosts` to access services by hostname:

```
127.0.0.1  jamesmassucco.com blog.jamesmassucco.com travel.jamesmassucco.com assets.jamesmassucco.com games.jamesmassucco.com
```

The Traefik dashboard is available at `http://localhost:8080`.

---

## 2. CI Integration Tests

**Workflow:** `.github/workflows/docker-integration.yml`  
**Composite actions:** `.github/actions/start-service`, `.github/actions/stop-service`  
**Script called:** `scripts/start_service.sh <service>`  
**Compose file used:** `docker-compose.yml` (production Compose, no local overrides)

### Purpose

Verify that each service starts correctly and its endpoints respond as expected. Runs on
every pull request, push to `main`, and on manual dispatch.

### How it works

Each service has its own job. The `start-service` action:
1. Creates the `web` Docker network.
2. Calls `scripts/start_service.sh <service>`, which builds the image and runs
   `docker compose up -d --build --wait`.
3. Tests run directly against the container (e.g. `docker exec <container> ...`).
4. The `stop-service` action tears down containers with `docker compose down --remove-orphans`.

The networking job is handled directly in the workflow (not via the composite actions)
because it has additional setup steps (generating test credentials, touching `acme.json`)
and skips `cloudflare-ddns` since DNS propagation is not testable in CI.

### Adding tests for a new service

1. Add a new job to `docker-integration.yml`.
2. Use the `start-service` / `stop-service` composite actions.
3. Add test steps that call endpoints inside the container.

---

## 3. Production Deployment

**Workflow:** `.github/workflows/deploy.yml`  
**Trigger:** Push to `main` (deploys all services) or `workflow_dispatch` (selective)  
**Script called:** `scripts/start_service.sh <service>` (on the server over SSH)

### Purpose

Deploy the current state of `main` to the production VPS. Images are pre-built by
`build-and-push.yml` and pulled from GHCR; the archive provides config files and
`networking/.env`.

### How it works

1. Connects to the server via Tailscale VPN.
2. Writes `networking/.env` from the `NETWORKING_ENV` secret.
3. Creates a `.tar.gz` archive of the repo (excluding `.git`, `node_modules`, etc.) and
   appends `networking/.env`.
4. SCPs the archive to `/tmp/homelab-deploy.tar.gz` on the server.
5. SSHes in, extracts to `/opt/homelab`, and calls `start_service.sh <service>` for each
   enabled service in dependency order:
   `networking → shared-assets → homepage → blog → travel → games`
6. `start_service.sh` pulls the pre-built image from GHCR and runs
   `docker compose up -d --wait`.

### Selective deployment

On `workflow_dispatch`, each service has a boolean checkbox (default: true). Only checked
services are deployed. On push to `main`, all services are deployed.

### Required secrets

| Secret | Description |
|--------|-------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale OAuth client ID |
| `TAILSCALE_OAUTH_SECRET` | Tailscale OAuth secret |
| `SSH_PRIVATE_KEY` | Private key for SSH into the server |
| `SERVER_HOST` | Tailscale hostname or IP of the server |
| `SERVER_USER` | SSH username on the server |
| `NETWORKING_ENV` | Full contents of `networking/.env` |

---

## 4. Staging Deployment

**Workflow:** `.github/workflows/deploy-staging.yml`  
**Trigger:** `workflow_dispatch` only (always manual)  
**Script called:** `scripts/start_service.sh <service> --staging` (on the server over SSH)  
**Compose files used:** `docker-compose.staging.yml` (per service)

### Purpose

Deploy a specific image tag to `*.staging.jamesmassucco.com` for testing before it reaches
production. Staging runs on the same server as production but uses separate container
names, Traefik routers, and (for `travel`) a separate Docker volume.

See `staging-plan.md` for the full architecture and one-time setup steps (DNS, TLS,
OAuth app redirect URI).

### How it works

Identical to the production workflow except:
- Uses `STAGING_NETWORKING_ENV` secret (which includes `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET`).
- Passes `STAGING_IMAGE_TAG` to `start_service.sh --staging`, which uses
  `docker-compose.staging.yml` instead of `docker-compose.yml`.
- Supports an optional `seed_from_prod` step that copies the production travel volume into
  the staging volume before deploying.

### Workflow inputs

| Input | Default | Description |
|-------|---------|-------------|
| `image_tag` | `latest` | GHCR image tag to deploy (e.g. `sha-abc1234`) |
| `seed_from_prod` | `false` | Copy production travel data to staging before deploying |
| `networking` | `false` | Deploy staging oauth2-proxy |
| `shared-assets` | `true` | Deploy staging shared-assets |
| `homepage` | `true` | Deploy staging homepage |
| `blog` | `true` | Deploy staging blog |
| `travel` | `true` | Deploy staging travel |
| `games` | `true` | Deploy staging games |

### Upgrade testing workflow

1. Trigger `deploy-staging.yml` with `image_tag=sha-<old-tag>` and `seed_from_prod=true`.
   Staging now mirrors the current production state.
2. Trigger `deploy-staging.yml` again with `image_tag=sha-<new-tag>`.
3. Verify staging data survived the upgrade at `travel.staging.jamesmassucco.com`.
4. If verified, trigger production `deploy.yml` to promote the same tag.

### Required secrets

Shares most secrets with production. One additional secret is required:

| Secret | Description |
|--------|-------------|
| `STAGING_NETWORKING_ENV` | `networking/.env` contents including `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET` |

---

## Staging subdomains

| URL | Service |
|-----|---------|
| `staging.jamesmassucco.com` | homepage |
| `blog.staging.jamesmassucco.com` | blog |
| `travel.staging.jamesmassucco.com` | travel |
| `games.staging.jamesmassucco.com` | games |
| `assets.staging.jamesmassucco.com` | shared-assets |
| `oauth.staging.jamesmassucco.com` | staging OAuth2-proxy |

---

## Compose file reference

| File | Used by |
|------|---------|
| `<service>/docker-compose.yml` | Production, CI integration tests |
| `<service>/docker-compose.local.yml` | Local development (overlaid on base) |
| `<service>/docker-compose.staging.yml` | Staging (standalone, not an overlay) |
| `networking/docker-compose.local.yml` | Local development Traefik (HTTP only) |
| `networking/docker-compose.staging.yml` | Staging OAuth2-proxy (standalone) |

---

## Choosing the right deployment method

| Situation | Use |
|-----------|-----|
| Actively developing a feature | Local development (`start_local.sh`) |
| Validating a PR builds and serves correctly | CI integration tests (automatic on PR) |
| Checking a specific image tag against real data before merging | Staging deploy |
| Releasing to production after merge | Production deploy (automatic on push to `main`) |
| Rolling back production to a previous build | Production `deploy.yml` dispatch with `sha-<tag>` in `docker-compose.yml` image field |
