# GitHub Secrets

This document describes all GitHub secrets required for the CI/CD workflows in this repository and how to manage them.

## How to Add a Secret

1. Navigate to the repository on GitHub.
2. Click **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
4. Enter the secret **Name** and **Value**, then click **Add secret**.

---

## Required Secrets

### Deployment Infrastructure

| Secret            | Description                                                                                                                                     |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `SSH_PRIVATE_KEY` | Private SSH key used to connect to the deployment server. The corresponding public key must be added to `~/.ssh/authorized_keys` on the server. |
| `SERVER_HOST`     | Hostname or IP address of the deployment server (reachable via Tailscale).                                                                      |
| `SERVER_USER`     | SSH username for the deployment server.                                                                                                         |

### Tailscale VPN

The deploy workflow connects to the server over a Tailscale VPN. These credentials come from a [Tailscale OAuth client](https://tailscale.com/kb/1215/oauth-clients) with the `tag:github` tag.

| Secret                      | Description                                           |
| --------------------------- | ----------------------------------------------------- |
| `TAILSCALE_OAUTH_CLIENT_ID` | OAuth client ID from the Tailscale admin console.     |
| `TAILSCALE_OAUTH_SECRET`    | OAuth client secret from the Tailscale admin console. |

### Networking Configuration (`NETWORKING_ENV`)

`NETWORKING_ENV` is a single multi-line secret that contains the entire contents of `networking/.env`. The deploy workflow writes this secret to disk as `networking/.env` before building the archive.

Required keys within `NETWORKING_ENV`:

| Key                           | Description                                                                                                                                |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `CLOUDFLARE_API_EMAIL`        | Email address for the Cloudflare account.                                                                                                  |
| `CLOUDFLARE_API_TOKEN`        | Cloudflare API token with DNS edit permissions (used by Traefik for ACME and by cloudflare-ddns).                                          |
| `CLOUDFLARE_TRUSTED_IPS`      | Comma-separated list of Cloudflare IP ranges to trust for `X-Forwarded-For` headers.                                                       |
| `GOOGLE_OAUTH2_CLIENT_ID`     | Google OAuth2 client ID (from Google Cloud Console).                                                                                       |
| `GOOGLE_OAUTH2_CLIENT_SECRET` | Google OAuth2 client secret.                                                                                                               |
| `GOOGLE_OAUTH2_COOKIE_SECRET` | Random 16-byte hex string used to sign OAuth2 session cookies (generate with `python3 -c "import secrets; print(secrets.token_hex(16))"`). |
| `OAUTH2_AUTHORIZED_EMAILS`    | Comma-separated list of Google email addresses allowed to authenticate.                                                                    |

Example format for `NETWORKING_ENV`:

```
CLOUDFLARE_API_EMAIL=you@example.com
CLOUDFLARE_API_TOKEN=your-token
CLOUDFLARE_TRUSTED_IPS=103.21.244.0/22,...
GOOGLE_OAUTH2_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH2_COOKIE_SECRET=<16-byte hex>
OAUTH2_AUTHORIZED_EMAILS=you@example.com
```

### Application Secrets

| Secret         | Description                                                                                                                                                                                           | Used By         |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `TMDB_API_KEY` | API key for [The Movie Database (TMDB)](https://developer.themoviedb.org/). Used by the movie picker feature. Obtain one by registering at [themoviedb.org](https://www.themoviedb.org/settings/api). | `tools` service |
