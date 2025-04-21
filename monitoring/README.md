# Monitoring
We use Prometheus to collect monitoring metrics on the servers in the cluster.

To start monitoring, run `~/devel/homelab/monitoring/prometheus/start.sh`

## Node Exporter
Node exporter handles collecting metrics on the server

## Prometheus
Prometheus collects metrics from node exporter and makes them available for querying.
