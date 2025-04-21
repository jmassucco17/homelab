# Monitoring
We use Prometheus to collect monitoring metrics on the servers in the cluster.

To start monitoring, run `~/devel/homelab/monitoring/prometheus/start.sh`

See https://chatgpt.com/share/6805952e-091c-8003-8a0a-6d829164ada2 for more details

## Node Exporter
Node exporter handles collecting metrics on the server

## Prometheus
Prometheus collects metrics from node exporter and makes them available for querying.

Access at: [http://ubuntu-server-1.local.:9090](http://ubuntu-server-1.local.:9090)

Example queries:
```
# CPU
rate(node_cpu_seconds_total{mode="user"}[1m])

# RAM
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / (1024^3)

# Network traffic
rate(node_network_receive_bytes_total[1m])
rate(node_network_transmit_bytes_total[1m])

# Available disk space
node_filesystem_avail_bytes / node_filesystem_size_bytes
node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}

# System load
node_load1
```

## Grafana
Grafana provides visualiation of the metrics

Access at: [grafana.jamesmassucco.com](grafana.jamesmassucco.com)

## Traefik
Traefik provides proxying. It also has a dashboard (turned off by default).

NOTE: Must provide an `.env` file in `monitoring/` that contains:
```sh
CF_API_EMAIL=<cloudflare email>
CF_DNS_API_TOKEN=<cloudflare token with DNS Edit and Zone Read permissions>
TRAEFIK_BASIC_AUTH=<htpasswd hash>
```