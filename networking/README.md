# Networking Configuration

## Traefik

Traefik provides reverse proxying. It also has a dashboard ([traefik.jamesmassucco.com](https://traefik.jamesmassucco.com/dashboard/#/)).

## OAuth2-Proxy

OAuth2-Proxy is configured as an authentication middleware for traefik. Multiple services (including the traefik dashboard) utilize Google OAuth using this method. The primary purpose is to enable some manner of user traffic and maintain the ability to ban any detected abusers.

## Cloudflare DDNS

This service automatically updates Cloudflare with our latest public IP address every 5 minutes, so that they always route traffic to the right place.

## Update Cloudflare script

The `update_cloudlare.sh` script queries the latest Cloudflare public IP address ranges and adds them to "allow lists" for Traefik and ufw

This script is called as part of `start.sh` or can be called on its own.
