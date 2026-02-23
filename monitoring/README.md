# monitoring

Lightweight monitoring module that collects metrics and logs from the VPS and ships them
to **Grafana Cloud** (managed Mimir + Loki). No self-hosted Grafana or Prometheus DB.

## Architecture

```
VPS
└── Docker (internal_metrics network)
    ├── node-exporter   → host metrics (CPU, RAM, disk, network)
    ├── cadvisor        → Docker container metrics
    └── alloy           → scrapes metrics, collects logs
            │
            ▼ (outbound HTTPS)
    Grafana Cloud
    ├── Mimir  (Prometheus-compatible metric storage)
    └── Loki   (log storage)
            │
            ▼
    grafana.com  (dashboards — no self-hosted Grafana needed)
```

## Configuration

Alloy reads its config from `alloy-config.alloy` (River syntax). It scrapes three targets:

| Target | Address | Metrics |
|--------|---------|---------|
| node-exporter | `node-exporter:9100` | Host system (CPU, RAM, disk, network) |
| cAdvisor | `cadvisor:8080` | Docker container resource usage |
| Traefik | `traefik:8082` | Request counts, latencies, TLS cert expiry |

Log collection uses `loki.source.docker` to tail all container logs via the Docker socket.

## Secrets

Five values must exist in `monitoring/.env` at deploy time (written by `_deploy.yml`):

| Variable | Description |
|----------|-------------|
| `GRAFANA_CLOUD_PROM_URL` | Prometheus remote_write endpoint |
| `GRAFANA_CLOUD_PROM_USER` | Prometheus username / instance ID |
| `GRAFANA_CLOUD_LOKI_URL` | Loki push endpoint |
| `GRAFANA_CLOUD_LOKI_USER` | Loki username / instance ID |
| `GRAFANA_CLOUD_API_KEY` | API token with `metrics:write` and `logs:write` scopes |

See `docs/secrets.md` for how to obtain these values.

## Networking

All containers share the `internal_metrics` external Docker network (created alongside
`web` at deploy time). Traefik also joins `internal_metrics` so Alloy can scrape it.
The metrics port (`8082`) is **not** published to the host.

## Dashboards

Import these community dashboards in Grafana Cloud (Dashboards → New → Import):

| Dashboard | Grafana.com ID |
|-----------|----------------|
| Node Exporter Full | `1860` |
| cAdvisor | `14282` |
