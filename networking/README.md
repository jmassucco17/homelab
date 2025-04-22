# Networking Configuration

## Traefik
Traefik provides reverse proxying. It also has a dashboard (turned off by default).

NOTE: Must provide an `.env` file in `reverse-proxy/` that contains:
```sh
# Cloudflare Auth
CLOUDFLARE_API_EMAIL=<email>
CLOUDFLARE_API_TOKEN=<token>

# DDNS Config
DOMAINS=grafana.jamesmassucco.com,traefik.jamesmassucco.com
PROXIED=false
TZ=America/Los_Angeles

# Traefik Auth
TRAEFIK_BASIC_AUTH=<htpasswd hash>
```

## Cloudflare DDNS
This service automatically updates Cloudflare with our latest public IP address every 5 minutes, so that they always route traffic to the right place.

## Update Cloudflare script
The `update_cloudlare.sh` script queries the latest Cloudflare public IP address ranges and adds them to "allow lists" for Traefik and ufw

This script is called as part of `start.sh` or can be called on its own.