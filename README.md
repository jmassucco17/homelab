# Homelab

Welcome to my homelab project!

## Webpages

- Homepage: [jamesmassucco.com](https://jamesmassucco.com)
- Blog: [blog.jamesmassucco.com](https://blog.jamesmassucco.com/)
- Travel Maps: [maps.jamesmassucco.com](https://maps.jamesmassucco.com)

## Service Dashboards

- Traefik: [traefik.jamesmassucco.com](https://traefik.jamesmassucco.com)
- Whoami: [whoami.jamesmassucco.com](https://whoami.jamesmassucco.com)

## Local Development

Use `scripts/start_local.sh` to run one or more services locally without touching real DNS.
This starts a lightweight HTTP-only traefik (no Cloudflare DDNS, no OAuth) and builds the
requested services.

```bash
# Start all services
./scripts/start_local.sh

# Start specific services
./scripts/start_local.sh blog
./scripts/start_local.sh blog travel/photos
```

Services can be accessed at `http://localhost:<port>` where `<port>` can be found in the
associated `docker-compose.local.yml` for each service. The traefik dashboard is always
available at `http://localhost:8080`.

To access services by hostname instead (matching production URLs), add to `/etc/hosts`:

```
127.0.0.1  jamesmassucco.com blog.jamesmassucco.com travel.jamesmassucco.com assets.jamesmassucco.com
```

## External Services

- Cloudflare provides domain registration and DNS, as well as proxying and DOS protection
- UptimeRobot provides external monitoring of website availability
