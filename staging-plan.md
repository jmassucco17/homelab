# Staging Environment Plan

## Goals

1. **Mirror production** — a `*.staging.jamesmassucco.com` environment that exercises the
   same Traefik, OAuth, TLS, and Cloudflare infrastructure as production.
2. **Version-to-version upgrade testing** — deploy a specific image tag to staging, run
   the upgrade, and confirm data integrity before the change ever reaches production.
3. **End-to-end CI gate** — the staging deploy workflow is triggered by a PR or manually,
   completing a full deploy test before code merges to `main`.
4. **Data persistence validation** — staging has its own persistent volumes that survive
   container restarts and image upgrades (mirroring the behaviour we care about in prod).

---

## Architecture Overview

### Approach: co-located staging on the same server

Both environments run on the same VPS. A single Traefik instance already listens on port
443 and routes traffic based on `Host()` rules. Staging services join the same `web` Docker
network so Traefik can reach them, but use different hostnames, container names, router
names, and volumes.

```
Internet → Cloudflare (proxied)
         → Server :443 → Traefik (shared instance)
                              ├── *.jamesmassucco.com          → production containers
                              └── *.staging.jamesmassucco.com  → staging containers
```

**Why not a separate server?**
A homelab doesn't justify the cost and operational overhead of a second machine. Staging
traffic is low-volume and the workload fits comfortably alongside production on a single
VPS.

**Why not a separate Traefik instance?**
Only one process can bind port 443. Re-using the existing Traefik keeps configuration
simple; staging containers simply carry different `traefik.http.routers.*` labels.

---

## Phase 1 — DNS and TLS

### 1.1 Cloudflare DNS — one wildcard record

Add a single proxied CNAME in the Cloudflare dashboard:

| Name | Type | Content | Proxied |
|------|------|---------|---------|
| `*.staging` | CNAME | `jamesmassucco.com` | ✅ yes |

All `*.staging.jamesmassucco.com` subdomains will then route through Cloudflare to the
same server IP as production.

### 1.2 DDNS

The `cloudflare-ddns` container in `networking/docker-compose.yml` keeps the root A
record (`jamesmassucco.com`) pointing at the server's current public IP. The wildcard
CNAME added above chains off that A record, so **no extra DDNS entry is required** for
staging subdomains.

If `staging.jamesmassucco.com` itself (without a subdomain) needs to resolve, add it to
the `DOMAINS` list in the `cloudflare-ddns` service, but this is optional.

### 1.3 TLS certificates

Traefik already issues per-subdomain certificates via the `cloudflare` ACME DNS-challenge
resolver. Every staging service router that specifies
`traefik.http.routers.<name>.tls.certresolver=cloudflare` will automatically receive a
valid cert for its `*.staging.jamesmassucco.com` hostname — no extra configuration
needed.

For lower ACME rate-limit exposure a wildcard cert can be issued once and reused. To do
this, add the following to the Traefik command in `networking/docker-compose.yml`:

```yaml
- '--certificatesresolvers.cloudflare.acme.domains[0].main=jamesmassucco.com'
- '--certificatesresolvers.cloudflare.acme.domains[0].sans=*.jamesmassucco.com,*.staging.jamesmassucco.com'
```

Then staging routers reference it with `tls.certresolver=cloudflare` and Traefik serves
the shared wildcard cert. This is optional but reduces the number of ACME requests.

---

## Phase 2 — Staging OAuth2-Proxy

Production OAuth uses `oauth2-proxy` with cookie domain `.jamesmassucco.com`. Staging
needs its own instance with cookie domain `.staging.jamesmassucco.com` so that prod and
staging sessions are completely independent.

### 2.1 Add staging oauth2-proxy to `networking/docker-compose.yml`

```yaml
  oauth2-proxy-staging:
    image: quay.io/oauth2-proxy/oauth2-proxy:v7.6.0
    container_name: oauth2-proxy-staging
    environment:
      OAUTH2_PROXY_PROVIDER: google
      OAUTH2_PROXY_CLIENT_ID: ${GOOGLE_OAUTH2_CLIENT_ID}
      OAUTH2_PROXY_CLIENT_SECRET: ${GOOGLE_OAUTH2_CLIENT_SECRET}
      OAUTH2_PROXY_EMAIL_DOMAINS: '*'
      OAUTH2_PROXY_AUTHENTICATED_EMAILS: ${OAUTH2_AUTHORIZED_EMAILS}
      OAUTH2_PROXY_REDIRECT_URL: https://oauth.staging.jamesmassucco.com/oauth2/callback
      OAUTH2_PROXY_COOKIE_SECRET: ${GOOGLE_OAUTH2_STAGING_COOKIE_SECRET}
      OAUTH2_PROXY_COOKIE_DOMAIN: .staging.jamesmassucco.com
      OAUTH2_PROXY_COOKIE_SECURE: true
      OAUTH2_PROXY_COOKIE_SAMESITE: lax
      OAUTH2_PROXY_SIGN_IN_PAGE: auto
      OAUTH2_PROXY_SKIP_PROVIDER_BUTTON: true
      OAUTH2_PROXY_WHITELIST_DOMAINS: .staging.jamesmassucco.com
      OAUTH2_PROXY_SET_XAUTHREQUEST: true
      OAUTH2_PROXY_REVERSE_PROXY: true
      OAUTH2_PROXY_HTTP_ADDRESS: 0.0.0.0:4180
      OAUTH2_PROXY_UPSTREAMS: static://200
      OAUTH2_PROXY_SHOW_DEBUG_ON_ERROR: true
    networks:
      - web
    labels:
      - traefik.enable=true
      - traefik.http.routers.oauth-staging.rule=Host(`oauth.staging.jamesmassucco.com`)
      - traefik.http.routers.oauth-staging.entrypoints=websecure
      - traefik.http.routers.oauth-staging.tls.certresolver=cloudflare
      - traefik.http.services.oauth-staging.loadbalancer.server.port=4180
    restart: unless-stopped
```

### 2.2 Define the `oauth-auth-staging` middleware

Add to the Traefik container's labels in `networking/docker-compose.yml`:

```yaml
- traefik.http.middlewares.oauth-auth-staging.forwardauth.address=https://oauth.staging.jamesmassucco.com/
- traefik.http.middlewares.oauth-auth-staging.forwardauth.trustForwardHeader=true
- traefik.http.middlewares.oauth-auth-staging.forwardauth.authResponseHeaders=X-Auth-Request-User,X-Auth-Request-Email
```

### 2.3 Google OAuth app redirect URI

Add `https://oauth.staging.jamesmassucco.com/oauth2/callback` to the **Authorized
redirect URIs** of the existing Google OAuth application (or create a second app). The
client ID and secret can be shared between prod and staging.

### 2.4 New environment variable

Add `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET` to `networking/.env`. This is a separate
32-byte random secret so staging and production session cookies are cryptographically
independent:

```bash
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

---

## Phase 3 — Per-Service `docker-compose.staging.yml` Overrides

Each service directory gets a `docker-compose.staging.yml` that overrides:
- **`container_name`** — prefix `staging-` to avoid collisions with production containers
- **Traefik labels** — staging hostnames, staging router names, `oauth-auth-staging`
  middleware where applicable
- **`image` tag** — parameterised as `${STAGING_IMAGE_TAG:-latest}` so CI can pin a
  specific SHA
- **Named volumes** — staging-prefixed to keep data completely separate from production

The base `docker-compose.yml` is always loaded first; the staging override only changes
what needs to differ.

### 3.1 `networking/docker-compose.staging.yml`

Adds the `oauth2-proxy-staging` container (see Phase 2) and the staging OAuth middleware
labels on the Traefik container without touching the production settings.

### 3.2 `shared-assets/docker-compose.staging.yml`

```yaml
services:
  shared-assets:
    container_name: staging-shared-assets
    image: ghcr.io/jmassucco17/homelab/shared-assets:${STAGING_IMAGE_TAG:-latest}
    labels:
      - traefik.enable=true
      - traefik.http.routers.shared-assets-staging.rule=Host(`assets.staging.jamesmassucco.com`)
      - traefik.http.routers.shared-assets-staging.entrypoints=websecure
      - traefik.http.routers.shared-assets-staging.tls.certresolver=cloudflare
      - traefik.http.services.shared-assets-staging.loadbalancer.server.port=80
      - traefik.http.routers.shared-assets-staging.middlewares=ratelimit
```

### 3.3 `homepage/docker-compose.staging.yml`

```yaml
services:
  homepage:
    container_name: staging-homepage
    image: ghcr.io/jmassucco17/homelab/homepage:${STAGING_IMAGE_TAG:-latest}
    labels:
      - traefik.enable=true
      - traefik.http.routers.homepage-staging.rule=Host(`staging.jamesmassucco.com`)
      - traefik.http.routers.homepage-staging.entrypoints=websecure
      - traefik.http.routers.homepage-staging.tls.certresolver=cloudflare
      - traefik.http.routers.homepage-staging.tls=true
      - traefik.http.services.homepage-staging.loadbalancer.server.port=80
```

### 3.4 `blog/docker-compose.staging.yml`

Blog posts are markdown files that live in the `posts/` directory. In production they are
bind-mounted from the repo checkout. For staging, the same files are used (staging tests
the rendering logic, not a different set of posts), so no separate volume is needed.

```yaml
services:
  blog:
    container_name: staging-blog
    image: ghcr.io/jmassucco17/homelab/blog:${STAGING_IMAGE_TAG:-latest}
    labels:
      - traefik.enable=true
      - traefik.http.routers.blog-staging.rule=Host(`blog.staging.jamesmassucco.com`)
      - traefik.http.routers.blog-staging.entrypoints=websecure
      - traefik.http.routers.blog-staging.tls=true
      - traefik.http.routers.blog-staging.tls.certresolver=cloudflare
      - traefik.http.routers.blog-staging.middlewares=ratelimit
      - traefik.http.services.blog-staging.loadbalancer.server.port=8000
```

### 3.5 `travel/docker-compose.staging.yml`

Travel has a persistent `data-volume` that holds photos and the SQLite database. Staging
gets its own named volume so production data is never touched.

```yaml
services:
  travel:
    container_name: staging-travel
    image: ghcr.io/jmassucco17/homelab/travel:${STAGING_IMAGE_TAG:-latest}
    volumes:
      - staging-travel-data:/data
    labels:
      - traefik.enable=true

      # Admin routes — require staging OAuth
      - traefik.http.routers.travel-admin-staging.rule=Host(`travel.staging.jamesmassucco.com`) && PathPrefix(`/photos/admin`)
      - traefik.http.routers.travel-admin-staging.entrypoints=websecure
      - traefik.http.routers.travel-admin-staging.tls.certresolver=cloudflare
      - traefik.http.routers.travel-admin-staging.middlewares=oauth-auth-staging,ratelimit
      - traefik.http.routers.travel-admin-staging.priority=100

      # Public routes
      - traefik.http.routers.travel-public-staging.rule=Host(`travel.staging.jamesmassucco.com`)
      - traefik.http.routers.travel-public-staging.entrypoints=websecure
      - traefik.http.routers.travel-public-staging.tls.certresolver=cloudflare
      - traefik.http.routers.travel-public-staging.middlewares=ratelimit
      - traefik.http.routers.travel-public-staging.priority=50

      - traefik.http.services.travel-staging.loadbalancer.server.port=8000

volumes:
  staging-travel-data:
    name: staging-travel-data
```

### 3.6 `games/docker-compose.staging.yml`

```yaml
services:
  games:
    container_name: staging-games
    image: ghcr.io/jmassucco17/homelab/games:${STAGING_IMAGE_TAG:-latest}
    labels:
      - traefik.enable=true
      - traefik.http.routers.games-staging.rule=Host(`games.staging.jamesmassucco.com`)
      - traefik.http.routers.games-staging.entrypoints=websecure
      - traefik.http.routers.games-staging.tls=true
      - traefik.http.routers.games-staging.tls.certresolver=cloudflare
      - traefik.http.routers.games-staging.middlewares=ratelimit
      - traefik.http.services.games-staging.loadbalancer.server.port=8000
```

---

## Phase 4 — Server-Side Deployment Script

Update `scripts/start_service.sh` to accept a `--staging` flag. When set, the compose
invocation appends the staging override file and passes `STAGING_IMAGE_TAG`.

```bash
# Usage:
#   scripts/start_service.sh blog
#   scripts/start_service.sh blog --staging
#   STAGING_IMAGE_TAG=sha-abc1234 scripts/start_service.sh travel --staging
```

Implementation sketch:

```bash
STAGING=false
for arg in "$@"; do
  [[ "$arg" == "--staging" ]] && STAGING=true
done
SERVICE="${1:?Usage: $0 <service> [--staging]}"

COMPOSE_FILES="-f docker-compose.yml"
if [[ "$STAGING" == "true" ]]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.staging.yml"
fi

sudo STAGING_IMAGE_TAG="${STAGING_IMAGE_TAG:-latest}" \
  docker compose $COMPOSE_FILES up -d --wait
```

---

## Phase 5 — CI/CD: `deploy-staging.yml` Workflow

Create `.github/workflows/deploy-staging.yml`. It mirrors `deploy.yml` with these
differences:

| Aspect | Production (`deploy.yml`) | Staging (`deploy-staging.yml`) |
|--------|--------------------------|-------------------------------|
| Trigger | push to `main` or `workflow_dispatch` | `workflow_dispatch` only (manual); optionally on `pull_request` |
| Image tag | `latest` | `sha-<short>` of the commit being tested (input) |
| Networking env | `NETWORKING_ENV` secret | `STAGING_NETWORKING_ENV` secret |
| `start_service.sh` call | `start_service.sh <svc>` | `start_service.sh <svc> --staging` |
| Default deploy-all | yes (on push) | no (always manual selection) |

### Workflow inputs

```yaml
on:
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'Image tag to deploy (e.g. sha-abc1234, or latest)'
        default: 'latest'
        required: false
      networking:
        description: 'Deploy staging networking (OAuth proxy)'
        type: boolean
        default: false
      shared-assets:
        description: 'Deploy shared-assets'
        type: boolean
        default: true
      homepage:
        description: 'Deploy homepage'
        type: boolean
        default: true
      blog:
        description: 'Deploy blog'
        type: boolean
        default: true
      travel:
        description: 'Deploy travel'
        type: boolean
        default: true
      games:
        description: 'Deploy games'
        type: boolean
        default: true
```

The `image_tag` input lets a developer pick a specific SHA tag (built by
`build-and-push.yml`) to deploy to staging without touching `main` or `latest`.

### Secrets

| Secret | Notes |
|--------|-------|
| `TAILSCALE_OAUTH_CLIENT_ID` | shared with prod |
| `TAILSCALE_OAUTH_SECRET` | shared with prod |
| `SSH_PRIVATE_KEY` | shared with prod |
| `SERVER_HOST` | shared with prod (same server) |
| `SERVER_USER` | shared with prod |
| `STAGING_NETWORKING_ENV` | new — staging-specific networking `.env` |

The `STAGING_NETWORKING_ENV` secret contains the same fields as `NETWORKING_ENV` plus the
new `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET` variable.

---

## Phase 6 — Data Management

### 6.1 Persistent data inventory

| Service | Storage | Production volume |
|---------|---------|------------------|
| homepage | none (static) | — |
| blog | markdown files in `posts/` (version-controlled) | — |
| shared-assets | none (static) | — |
| travel | SQLite DB + uploaded photos at `/data` | `travel-site_data-volume` |
| games | none confirmed (stateless sessions) | — |

The `travel` service is the only one with meaningful persistent state.

### 6.2 Staging volume strategy

Staging keeps its own `staging-travel-data` volume. This volume is independent of the
production volume so upgrades can be tested without risking prod data.

**Three seeding options:**

| Option | Description | When to use |
|--------|-------------|-------------|
| **A — Empty** | Staging starts with an empty database | Testing new installs / schema creation |
| **B — Copy from prod** | `docker run --rm -v travel-site_data-volume:/src:ro -v staging-travel-data:/dst alpine cp -a /src/. /dst/` | Testing upgrades against real data |
| **C — Seed script** | A `scripts/seed_staging_data.sh` populates staging with a fixed set of synthetic photos/trips | Repeatable, no PII risk |

Option B is most valuable for testing version upgrades:

```bash
# On the server — copy prod travel data into staging volume
docker run --rm \
  -v travel-site_data-volume:/src:ro \
  -v staging-travel-data:/dst \
  alpine \
  sh -c "cp -a /src/. /dst/"
```

This can be added as an optional step in `deploy-staging.yml` behind a `seed_from_prod`
boolean input.

### 6.3 Testing an upgrade end-to-end

1. Trigger `deploy-staging.yml` with `image_tag=sha-<old>` and `seed_from_prod=true`.
2. Staging now mirrors the current production state.
3. Trigger `deploy-staging.yml` again with `image_tag=sha-<new>` (the candidate release).
4. Verify that staging data survived the upgrade (UI inspection, or an automated smoke
   test against `travel.staging.jamesmassucco.com`).
5. If verified, trigger production `deploy.yml` to promote the same SHA to prod.

---

## Phase 7 — Subdomains Summary

| Staging URL | Routes to |
|-------------|-----------|
| `staging.jamesmassucco.com` | staging homepage |
| `blog.staging.jamesmassucco.com` | staging blog |
| `travel.staging.jamesmassucco.com` | staging travel |
| `games.staging.jamesmassucco.com` | staging games |
| `assets.staging.jamesmassucco.com` | staging shared-assets |
| `oauth.staging.jamesmassucco.com` | staging OAuth2-proxy |

---

## Implementation Checklist

### Infrastructure
- [ ] Add `*.staging` wildcard CNAME in Cloudflare DNS (proxied, points to
  `jamesmassucco.com`)
- [ ] (Optional) Add `staging.jamesmassucco.com` to `cloudflare-ddns` DOMAINS list if a
  direct A record is needed
- [ ] (Optional) Configure Traefik wildcard cert for `*.staging.jamesmassucco.com` in
  `networking/docker-compose.yml`

### Networking / OAuth
- [ ] Add `oauth2-proxy-staging` service to `networking/docker-compose.yml`
- [ ] Add `oauth-auth-staging` middleware labels to the Traefik container
- [ ] Add `https://oauth.staging.jamesmassucco.com/oauth2/callback` to Google OAuth app
  Authorized Redirect URIs
- [ ] Generate `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET` and add to `networking/.env`

### Service Overrides
- [ ] Create `networking/docker-compose.staging.yml`
- [ ] Create `shared-assets/docker-compose.staging.yml`
- [ ] Create `homepage/docker-compose.staging.yml`
- [ ] Create `blog/docker-compose.staging.yml`
- [ ] Create `travel/docker-compose.staging.yml` (with `staging-travel-data` volume)
- [ ] Create `games/docker-compose.staging.yml`

### Scripts
- [ ] Update `scripts/start_service.sh` to accept `--staging` flag

### CI/CD
- [ ] Create `.github/workflows/deploy-staging.yml`
- [ ] Add `STAGING_NETWORKING_ENV` secret to GitHub repository settings

### Data
- [ ] (Optional) Create `scripts/seed_staging_data.sh` for repeatable synthetic data
- [ ] (Optional) Add `seed_from_prod` input to `deploy-staging.yml` that runs the volume
  copy step before deploying the new image

### Verification
- [ ] After initial setup, confirm `https://staging.jamesmassucco.com` loads correctly
- [ ] Confirm OAuth login works at `https://oauth.staging.jamesmassucco.com`
- [ ] Confirm `https://travel.staging.jamesmassucco.com` serves data from the staging
  volume (not the production volume)
- [ ] Perform one full upgrade test: deploy old tag → seed data → deploy new tag →
  verify data intact
