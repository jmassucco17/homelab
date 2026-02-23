# Grafana Cloud Monitoring Plan

## Overview

This document describes how to re-introduce lightweight monitoring to the Hetzner VPS
homelab using **Grafana Cloud** as the managed backend. The previous setup
(commit `2396060`) ran self-hosted Grafana, Prometheus, Loki, and Promtail as Docker
containers in a `monitoring/` module. That design worked on a beefy local mini PC but
adds unnecessary memory pressure and operational overhead on a small VPS.

The new design ships all data outbound to Grafana Cloud's free tier and removes every
self-hosted monitoring container except the collectors (node-exporter, cAdvisor, and
Grafana Alloy).

---

## Goals

- Lightweight: minimal resource impact on the VPS.
- No self-hosted Prometheus DB and no self-hosted Grafana or Loki.
- Collect the same signals as before: host metrics, container metrics, Traefik metrics,
  and container logs.
- No new public subdomains (dashboards live on `grafana.com`, not `grafana.jamesmassucco.com`).
- Secrets handled the same way as the rest of the repo (individual GitHub secrets →
  assembled into `monitoring/.env` at deploy time).
- No staging counterpart for monitoring (it is an operational tool, not a user-facing
  service).

---

## Architecture: Before vs. After

### Before (self-hosted, stripped out before Hetzner migration)

```
VPS
└── Docker
    ├── networking/
    │   └── traefik  ──────────────────────────► :8082 (Prometheus metrics, exposed publicly)
    └── monitoring/
        ├── prometheus     (scraped traefik, node-exporter, cadvisor; stored data locally)
        ├── node-exporter
        ├── cadvisor
        ├── loki           (stored logs locally on disk)
        ├── promtail       (tailed container logs → loki)
        └── grafana        (self-hosted; public subdomain grafana.jamesmassucco.com)
```

Problems: ~500 MB+ RAM for monitoring stack alone; persistent volumes for Prometheus and
Loki data; public subdomains and TLS certs for Grafana and Prometheus.

### After (Grafana Cloud, outbound push)

```
VPS
└── Docker
    ├── networking/
    │   └── traefik  ──► :8082 (metrics, internal_metrics network only, not exposed)
    └── monitoring/
        ├── node-exporter  (pid:host; scraped by Alloy)
        ├── cadvisor       (Docker socket; scraped by Alloy)
        └── alloy          (unified agent)
                │
                ├── scrapes node-exporter, cadvisor, traefik
                ├── tails Docker container logs via Docker socket
                │
                ▼ (outbound HTTPS)
        Grafana Cloud
        ├── Mimir   (Prometheus-compatible metric storage)
        └── Loki    (log storage)
                │
                ▼
        grafana.com  (dashboards, alerts — no self-hosted instance needed)
```

Benefits:
- Alloy + node-exporter + cAdvisor together use ~100 MB RAM.
- No persistent volumes for metric or log data.
- No public subdomains or TLS certs for monitoring.
- Grafana Cloud free tier: 10,000 active series, 50 GB logs/month — more than enough for
  a personal homelab.

---

## Component Decisions

| Component | Choice | Reason |
|-----------|--------|--------|
| Metrics storage | Grafana Cloud Mimir (managed) | No local disk; free tier is generous |
| Log storage | Grafana Cloud Loki (managed) | Same reasoning |
| Dashboards | grafana.com | No self-hosted Grafana needed |
| Collection agent | Grafana Alloy | Replaces Prometheus Agent + Promtail in one container; native Grafana Cloud integration |
| Host metrics | prom/node-exporter | Same as before; lightweight |
| Container metrics | gcr.io/cadvisor/cadvisor | Same as before |
| Traefik metrics | Re-enabled (internal only) | Scrapes existing Prometheus endpoint; no public exposure |

### Why Grafana Alloy instead of Prometheus Agent + Promtail?

Alloy is the officially recommended successor to Grafana Agent and Promtail. It handles
both metric scraping (with `prometheus.remote_write`) and log shipping (with
`loki.source.docker`) in a single process using a declarative River config language.
Running one container instead of two reduces overhead and simplifies config.

---

## Shared `internal_metrics` Docker Network

Traefik (in `networking/`) and the monitoring collectors (in `monitoring/`) live in
separate Docker Compose projects. For Alloy to scrape Traefik's metrics endpoint they
must share a Docker network.

The existing pattern in this repo is to declare shared networks as `external: true` and
create them once at startup (alongside the `web` network). The same approach applies here:

- Network name: `internal_metrics`
- Created by `start_service.sh networking` (add `docker network create internal_metrics`
  alongside the existing `docker network create web` in `_deploy.yml`).
- Traefik: joined to `internal_metrics` (metrics only, not routing traffic).
- All monitoring containers: joined to `internal_metrics`.
- The network is declared `internal: true` so containers on it cannot reach the internet
  directly (only Alloy breaks this via its own outbound connection, which is fine).

---

## New Module: `monitoring/`

### Files

```
monitoring/
├── docker-compose.yml      # node-exporter, cAdvisor, Alloy
├── alloy-config.alloy      # Grafana Alloy River config
└── README.md
```

No `Dockerfile` (all images are pulled from Docker Hub / GCR). No
`docker-compose.prod.yml` overlay (Traefik routing is not needed). No
`docker-compose.staging.yml` (monitoring has no staging counterpart).

### `docker-compose.yml`

```yaml
services:
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    pid: host
    command:
      - '--path.rootfs=/host'
    volumes:
      - /:/host:ro,rslave
    networks:
      - internal_metrics
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    networks:
      - internal_metrics
    restart: unless-stopped

  alloy:
    image: grafana/alloy:latest
    container_name: alloy
    volumes:
      - ./alloy-config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command:
      - run
      - /etc/alloy/config.alloy
      - --storage.path=/var/lib/alloy/data
    env_file:
      - .env
    networks:
      - internal_metrics
    depends_on:
      - node-exporter
      - cadvisor
    restart: unless-stopped

networks:
  internal_metrics:
    external: true
```

### `alloy-config.alloy`

```river
// ──────────────────────────────────────────────
// Metric scraping
// ──────────────────────────────────────────────

prometheus.scrape "node_exporter" {
  targets = [{"__address__" = "node-exporter:9100"}]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
}

prometheus.scrape "cadvisor" {
  targets = [{"__address__" = "cadvisor:8080"}]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
}

prometheus.scrape "traefik" {
  targets = [{"__address__" = "traefik:8082"}]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
}

prometheus.remote_write "grafana_cloud" {
  endpoint {
    url = env("GRAFANA_CLOUD_PROM_URL")
    basic_auth {
      username = env("GRAFANA_CLOUD_PROM_USER")
      password = env("GRAFANA_CLOUD_API_KEY")
    }
  }
}

// ──────────────────────────────────────────────
// Log collection
// ──────────────────────────────────────────────

discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

discovery.relabel "containers" {
  targets = discovery.docker.containers.targets
  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container"
  }
}

loki.source.docker "containers" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.containers.output
  forward_to = [loki.write.grafana_cloud.receiver]
}

loki.write "grafana_cloud" {
  endpoint {
    url = env("GRAFANA_CLOUD_LOKI_URL")
    basic_auth {
      username = env("GRAFANA_CLOUD_LOKI_USER")
      password = env("GRAFANA_CLOUD_API_KEY")
    }
  }
}
```

---

## Changes to Existing Modules

### `networking/docker-compose.yml`

Re-enable Traefik's Prometheus metrics endpoint and connect Traefik to `internal_metrics`.
The metrics port is **not** published to the host (no `ports:` entry); it is only
reachable inside `internal_metrics` by Alloy.

Changes:
1. Uncomment the three Prometheus metric flags in the `command:` block:
   ```yaml
   - '--metrics.prometheus=true'
   - '--metrics.prometheus.entrypoint=metrics'
   - '--entrypoints.metrics.address=:8082'
   ```
2. Add `internal_metrics` to Traefik's `networks:` list.
3. Declare `internal_metrics` as an external network at the bottom of the file.

### `_deploy.yml`

1. **Create `internal_metrics` network** alongside the existing `web` network creation
   in the remote SSH block:
   ```bash
   docker network create internal_metrics 2>/dev/null || true
   ```
2. **Write `monitoring/.env`** from Grafana Cloud secrets (similar to the `Write tools/.env`
   step):
   ```yaml
   - name: Write monitoring/.env
     env:
       GRAFANA_CLOUD_PROM_URL: ${{ secrets.GRAFANA_CLOUD_PROM_URL }}
       GRAFANA_CLOUD_PROM_USER: ${{ secrets.GRAFANA_CLOUD_PROM_USER }}
       GRAFANA_CLOUD_LOKI_URL: ${{ secrets.GRAFANA_CLOUD_LOKI_URL }}
       GRAFANA_CLOUD_LOKI_USER: ${{ secrets.GRAFANA_CLOUD_LOKI_USER }}
       GRAFANA_CLOUD_API_KEY: ${{ secrets.GRAFANA_CLOUD_API_KEY }}
     run: |
       {
         printf 'GRAFANA_CLOUD_PROM_URL=%s\n' "$GRAFANA_CLOUD_PROM_URL"
         printf 'GRAFANA_CLOUD_PROM_USER=%s\n' "$GRAFANA_CLOUD_PROM_USER"
         printf 'GRAFANA_CLOUD_LOKI_URL=%s\n' "$GRAFANA_CLOUD_LOKI_URL"
         printf 'GRAFANA_CLOUD_LOKI_USER=%s\n' "$GRAFANA_CLOUD_LOKI_USER"
         printf 'GRAFANA_CLOUD_API_KEY=%s\n' "$GRAFANA_CLOUD_API_KEY"
       } > monitoring/.env
   ```
3. **Include `monitoring/.env`** in the deployment archive (append alongside `tools/.env`
   when environment is `prod`).
4. **Add `monitoring` to the deploy services list** (production only; no staging flag
   needed). Add it after `networking` and before `shared-assets` in the deployment order
   to match the module ordering convention:
   `networking → monitoring → shared-assets → homepage → …`
5. **Add a `monitoring` boolean input** to the `_deploy.yml` and `build-and-deploy.yml`
   dispatch inputs (default: `true`), following the pattern of the other services.

### `_integration.yml`

1. Add `monitoring` to the `compose-validate` loop so the Compose file is syntax-checked
   on every PR.
2. Add a `monitoring` integration test job that:
   - Creates a stub `monitoring/.env` with placeholder Grafana Cloud values.
   - Creates the `internal_metrics` Docker network.
   - Starts `node-exporter` and `cadvisor` (not Alloy, since it would attempt outbound
     connections to Grafana Cloud that will fail in CI).
   - Verifies node-exporter responds on `:9100/metrics`.
   - Verifies cAdvisor responds on `:8080/metrics`.

### `.github/dependabot.yml`

Add a `docker` ecosystem entry for `/monitoring` so Dependabot keeps the Alloy,
node-exporter, and cAdvisor image tags up to date.

---

## New Secrets

These five secrets must be added to GitHub repository secrets (Settings → Secrets and
variables → Actions → Repository secrets) before the first production deployment.

| Secret | Description | How to obtain |
|--------|-------------|---------------|
| `GRAFANA_CLOUD_PROM_URL` | Prometheus remote_write endpoint | Grafana Cloud → Connections → Data sources → Prometheus → Details |
| `GRAFANA_CLOUD_PROM_USER` | Prometheus basic-auth username (numeric ID) | Same page, field "Username / Instance ID" |
| `GRAFANA_CLOUD_LOKI_URL` | Loki push endpoint | Grafana Cloud → Connections → Data sources → Loki → Details |
| `GRAFANA_CLOUD_LOKI_USER` | Loki basic-auth username (numeric ID) | Same page, field "Username / Instance ID" |
| `GRAFANA_CLOUD_API_KEY` | API key used as the password for both endpoints | Grafana Cloud → My Account → Access Policies → Create a policy with `metrics:write` and `logs:write` scopes, then generate a token |

These five values must also be added to `docs/secrets.md`.

---

## One-Time Manual Setup: Grafana Cloud

These steps are performed once before the first deployment. None of them require changes
to the repository.

1. **Create a Grafana Cloud account** at [grafana.com](https://grafana.com). Choose the
   free "Hobby" plan.

2. **Retrieve the Prometheus connection details:**
   - Navigate to: Home → Connections → Data sources → Prometheus → Connection details.
   - Copy the remote_write URL (e.g. `https://prometheus-prod-XX-prod-us-east-0.grafana.net/api/prom/push`).
   - Copy the Username / Instance ID (a numeric value, e.g. `123456`).

3. **Retrieve the Loki connection details:**
   - Navigate to: Home → Connections → Data sources → Loki → Connection details.
   - Copy the Loki push URL (e.g. `https://logs-prod-006.grafana.net/loki/api/v1/push`).
   - Copy the Username / Instance ID.

4. **Create an API key (Access Policy token):**
   - Navigate to: Home → My Account → Access Policies → Create access policy.
   - Grant scopes: `metrics:write`, `logs:write`.
   - Create a token and copy it. This is `GRAFANA_CLOUD_API_KEY`.
   - Store it immediately — it is only shown once.

5. **Add all five values as GitHub repository secrets** (see table in "New Secrets" section
   above).

6. **Import community dashboards** (optional but recommended):
   - In Grafana Cloud, go to Dashboards → New → Import.
   - Node Exporter Full: ID `1860`
   - cAdvisor: ID `14282`
   - These use the standard metric names emitted by node-exporter and cAdvisor.

---

## One-Time Server Setup

1. **Create the `internal_metrics` Docker network** (this is also handled automatically
   by `_deploy.yml` on the first deploy, but can be done manually first):
   ```bash
   docker network create internal_metrics
   ```

2. The `monitoring/` directory will be deployed to `/opt/homelab/monitoring/` by the
   deploy workflow. The `alloy-config.alloy` file is included in the deployment archive,
   so no manual file placement is needed.

---

## Implementation Checklist

The following tasks represent the full implementation. Each is a small, self-contained
change that can be done in order or batched into one PR.

### Repository changes

- [ ] Create `monitoring/docker-compose.yml`
- [ ] Create `monitoring/alloy-config.alloy`
- [ ] Create `monitoring/README.md`
- [ ] Update `networking/docker-compose.yml`: uncomment Traefik metrics flags, add
      `internal_metrics` network to Traefik, declare `internal_metrics` as external network
- [ ] Update `_deploy.yml`:
  - [ ] Add `monitoring` boolean input (default: `true`)
  - [ ] Add `Write monitoring/.env` step
  - [ ] Include `monitoring/.env` in the deploy archive
  - [ ] Add `docker network create internal_metrics` to the remote SSH block
  - [ ] Add `deploy_if_enabled monitoring "$DEPLOY_MONITORING"` call (after networking)
- [ ] Update `build-and-deploy.yml`: add `monitoring` boolean dispatch input
- [ ] Update `_integration.yml`:
  - [ ] Add `monitoring` to the `compose-validate` loop
  - [ ] Add `monitoring` integration test job (node-exporter + cAdvisor healthchecks only)
- [ ] Update `.github/dependabot.yml`: add `/monitoring` Docker entry
- [ ] Update `docs/secrets.md`: document the five new Grafana Cloud secrets

### Manual steps (not in the repo)

- [ ] Create Grafana Cloud account
- [ ] Retrieve Prometheus and Loki connection details
- [ ] Create Access Policy token with `metrics:write` + `logs:write` scopes
- [ ] Add five secrets to GitHub repository secrets
- [ ] Import community dashboards (node-exporter ID `1860`, cAdvisor ID `14282`)
- [ ] Verify data is flowing after first deploy (check Grafana Cloud Explore tab)

---

## Out of Scope

- **Alerting**: Grafana Cloud supports alert rules and notification channels. Setting up
  alerts (e.g. high CPU, disk nearly full) is valuable but is a separate concern. Do it
  after the data pipeline is confirmed working.
- **Staging monitoring**: The monitoring module is production-only. A staging instance
  of Alloy is unnecessary and would pollute the production Grafana Cloud workspace with
  test data.
- **Custom dashboards**: The imported community dashboards cover the initial use cases.
  Custom dashboards can be built iteratively in Grafana Cloud once data is flowing.
- **Uptime / blackbox monitoring**: Grafana Cloud's synthetic monitoring (free tier
  includes some probes) can check external endpoints. Worth exploring separately.
