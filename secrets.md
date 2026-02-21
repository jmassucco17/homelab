# Secrets Reference

This document lists every secret required to operate the homelab, where each one is used,
and how to generate or obtain it.

---

## GitHub Repository Secrets

These are configured under **Settings → Secrets and variables → Actions** in the GitHub
repository.

| Secret | Used by | Description |
|--------|---------|-------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | `deploy.yml`, `deploy-staging.yml` | Tailscale OAuth client ID for the GitHub Actions tag. Create under **Settings → OAuth clients** in the Tailscale admin console. |
| `TAILSCALE_OAUTH_SECRET` | `deploy.yml`, `deploy-staging.yml` | Tailscale OAuth secret paired with the client ID above. |
| `SSH_PRIVATE_KEY` | `deploy.yml`, `deploy-staging.yml` | Private key for SSH access to the production server. The corresponding public key must be in `~/.ssh/authorized_keys` on the server. |
| `SERVER_HOST` | `deploy.yml`, `deploy-staging.yml` | Tailscale hostname or IP address of the production server. |
| `SERVER_USER` | `deploy.yml`, `deploy-staging.yml` | SSH username on the production server (typically `root` or a deploy user). |
| `NETWORKING_ENV` | `deploy.yml` | Full contents of `networking/.env` for production. See [networking/.env fields](#networkingenv-fields) below. |
| `STAGING_NETWORKING_ENV` | `deploy-staging.yml` | Full contents of `networking/.env` for staging. Same fields as `NETWORKING_ENV` plus `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET`. See [staging additions](#staging-additions) below. |
| `TMDB_API_KEY` | `deploy.yml`, `deploy-staging.yml` | API key for [The Movie Database (TMDB)](https://developer.themoviedb.org/). Used by the movie picker feature. Obtain one by registering at [themoviedb.org](https://www.themoviedb.org/settings/api). |

---

## networking/.env Fields

Both `NETWORKING_ENV` and `STAGING_NETWORKING_ENV` are `.env` files loaded by
`networking/docker-compose.yml`. The following fields are required:

| Variable | Description | How to obtain |
|----------|-------------|---------------|
| `CLOUDFLARE_API_EMAIL` | Email address of the Cloudflare account | Cloudflare dashboard → Profile |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token with **Zone:DNS:Edit** permission for the `jamesmassucco.com` zone | Cloudflare dashboard → My Profile → API Tokens |
| `CLOUDFLARE_TRUSTED_IPS` | Comma-separated list of Cloudflare CDN IP ranges to trust for forwarded headers | [Cloudflare IP ranges](https://www.cloudflare.com/ips/) — use the IPv4 list |
| `GOOGLE_OAUTH2_CLIENT_ID` | Google OAuth 2.0 client ID | Google Cloud Console → APIs & Services → Credentials |
| `GOOGLE_OAUTH2_CLIENT_SECRET` | Google OAuth 2.0 client secret | Google Cloud Console → APIs & Services → Credentials |
| `GOOGLE_OAUTH2_COOKIE_SECRET` | 32-byte random secret for signing OAuth session cookies (production) | `python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| `OAUTH2_AUTHORIZED_EMAILS` | Comma-separated list of Google email addresses allowed to log in | Set to your own Google account(s) |

### Staging additions

`STAGING_NETWORKING_ENV` must include all of the above fields plus:

| Variable | Description | How to obtain |
|----------|-------------|---------------|
| `GOOGLE_OAUTH2_STAGING_COOKIE_SECRET` | 32-byte random secret for signing staging OAuth session cookies — **must be different from the production secret** | `python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` |

The staging OAuth proxy also needs `https://oauth.staging.jamesmassucco.com/oauth2/callback`
added to the Google OAuth app's **Authorized Redirect URIs** (Google Cloud Console →
Credentials → the OAuth 2.0 Client ID → Edit).
