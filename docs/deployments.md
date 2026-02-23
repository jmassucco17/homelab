# Deployment Guide

This document describes every way to deploy the homelab services, how they relate to each
other, and when to use each one.

---

## Overview

All three deployment modes share a common runtime: **`scripts/start_service.sh`**.
The script starts a single service by name, choosing the right Compose file(s) based on
the mode. The modes differ only in _which_ Compose files are used and _where_ the script
runs.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          scripts/start_service.sh                            │
│                                                                              │
│  No flags   → docker-compose.yml + docker-compose.prod.yml  (production)    │
│  --staging  → docker-compose.yml + docker-compose.staging.yml  (staging)    │
└──────────────────────────────────────────────────────────────────────────────┘
         ▲                    ▲                       ▲
         │                    │                       │
   CI integration       Production deploy       Staging deploy
   (docker-integration  (.github/workflows/     (.github/workflows/
    .yml via             build-and-deploy.yml)   build-and-deploy.yml
    start-service        environment=prod)        environment=staging)
    action)
```

---

## 1. CI Integration Tests

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

## 2. Production Deployment

**Workflow:** `.github/workflows/build-and-deploy.yml` (calls `_deploy.yml`)  
**Trigger:** Push to `main` (deploys all services) or `workflow_dispatch` (selective)  
**Script called:** `scripts/start_service.sh <service>` (on the server over SSH)

### Purpose

Deploy the current state of `main` to the production VPS. Images are pre-built by
`_build.yml` and pulled from GHCR; the archive provides config files and
`networking/.env`.

### How it works

1. Connects to the server via Tailscale VPN.
2. Assembles `networking/.env` from individual GitHub secrets.
3. Creates a `.tar.gz` archive of the repo (excluding `.git`, `node_modules`, etc.) and
   appends `networking/.env`.
4. SCPs the archive to `/tmp/homelab-deploy.tar.gz` on the server.
5. SSHes in, extracts to `/opt/homelab`, and calls `start_service.sh <service>` for each
   enabled service in dependency order:
   `networking → shared-assets → homepage → blog → games → tools → travel`
6. `start_service.sh` pulls the pre-built image from GHCR and runs
   `docker compose up -d --wait`.

### Selective deployment

On `workflow_dispatch`, each service has a boolean checkbox (default: true). Only checked
services are deployed. On push to `main`, all services are deployed.

### Required secrets

See [`docs/secrets.md`](secrets.md) for the full list of repository secrets that must be
configured before deployment.

---

## 3. Staging Deployment

**Workflow:** `.github/workflows/build-and-deploy.yml` (calls `_deploy.yml`)  
**Trigger:** `workflow_dispatch` only (select `staging` environment)  
**Script called:** `scripts/start_service.sh <service> --staging` (on the server over SSH)  
**Compose files used:** `docker-compose.yml` + `docker-compose.staging.yml` (per service, overlaid)

### Purpose

Deploy a specific image tag to `*.staging.jamesmassucco.com` for testing before it reaches
production. Staging runs on the same server as production but uses separate container
names, Traefik routers, and (for `travel`) a separate Docker volume. One-time setup steps
(DNS, TLS, OAuth app redirect URI) are covered in the checklist at the end of this doc.

### How it works

Identical to the production workflow except:

- The `environment` input is set to `staging` (auto-detected as `prod` on push to `main`).
- Passes `STAGING_IMAGE_TAG` to `start_service.sh --staging`, which overlays
  `docker-compose.staging.yml` on top of `docker-compose.yml` under an isolated
  `staging-<service>` Docker Compose project so production containers are never affected.
- Supports an optional `seed_from_prod` step that copies the production travel volume into
  the staging volume before deploying.

Staging and production share the same set of repository secrets. See
[`docs/secrets.md`](secrets.md) for the full list.

### Workflow inputs

| Input | Default | Description |
|-------|---------|-------------|
| `environment` | — | Set to `staging` |
| `seed_from_prod` | `false` | Copy production travel data to staging before deploying |
| `networking` | `true` | Deploy staging oauth2-proxy |
| `shared-assets` | `true` | Deploy staging shared-assets |
| `homepage` | `true` | Deploy staging homepage |
| `blog` | `true` | Deploy staging blog |
| `travel` | `true` | Deploy staging travel |
| `games` | `true` | Deploy staging games |
| `tools` | `true` | Deploy staging tools |

### Upgrade testing workflow

1. Trigger `build-and-deploy.yml` with `environment=staging`, `image_tag=sha-<old-tag>`, and `seed_from_prod=true`.
   Staging now mirrors the current production state.
2. Trigger again with `image_tag=sha-<new-tag>`.
3. Verify staging data survived the upgrade at `travel.staging.jamesmassucco.com`.
4. If verified, trigger production deploy (push to `main` or `workflow_dispatch` with `environment=prod`).

---

## Staging subdomains

| URL                                | Service              |
| ---------------------------------- | -------------------- |
| `staging.jamesmassucco.com`        | homepage             |
| `blog.staging.jamesmassucco.com`   | blog                 |
| `travel.staging.jamesmassucco.com` | travel               |
| `games.staging.jamesmassucco.com`  | games                |
| `assets.staging.jamesmassucco.com` | shared-assets        |
| `oauth.staging.jamesmassucco.com`  | staging OAuth2-proxy |

---

## Compose file reference

Every service directory follows the same layout:

| File                                    | Used by                 | Purpose                                                                             |
| --------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------- |
| `<service>/docker-compose.yml`          | Production, staging, CI | Base service definition (image, build, healthcheck, restart, `traefik.enable=true`) |
| `<service>/docker-compose.prod.yml`     | Production, CI          | Production-only overrides (named data volume for `travel`); also acts as sentinel for `start_service.sh` staging overlay logic |
| `<service>/docker-compose.staging.yml`  | Staging                 | Staging routing labels (Docker provider); separate volume for `travel`              |
| `networking/docker-compose.staging.yml` | Staging                 | Staging OAuth2-proxy (standalone)                                                   |
| `networking/config/dynamic.yml`         | Production              | Traefik middlewares (`ratelimit`, `oauth-auth`) and dashboard router                |
| `networking/config/<service>.yml`       | Production              | Per-service Traefik routers and backend definitions (file provider)                 |

---

## Choosing the right deployment method

| Situation                                                      | Use                                                                              |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Validating a PR builds and serves correctly                    | CI integration tests (automatic on PR)                                           |
| Checking a specific image tag against real data before merging | Staging deploy                                                                   |
| Releasing to production after merge                            | Production deploy (automatic on push to `main`)                                  |
| Rolling back production to a previous build                    | `build-and-deploy.yml` dispatch with `environment=prod`, uncheck rebuilt services |

## One-time staging setup

Before staging is usable for the first time, complete these manual steps:

1. Add a `*.staging` wildcard CNAME in Cloudflare DNS (proxied, pointing to
   `jamesmassucco.com`). This is a one-time static record — it doesn't need DDNS because it
   chains off the `jamesmassucco.com` A record which cloudflare-ddns already keeps current.
   The A record for `staging.jamesmassucco.com` is managed automatically by cloudflare-ddns
   (added to its DOMAINS list in `networking/docker-compose.yml`).
2. Add `https://oauth.staging.jamesmassucco.com/oauth2/callback` to the Google OAuth
   app's Authorized Redirect URIs.
3. Ensure all repository secrets from [`docs/secrets.md`](secrets.md) are configured.
4. Deploy staging networking once to start `oauth2-proxy-staging`:
   ```
   build-and-deploy.yml → environment=staging, networking=true, all others=false
   ```
