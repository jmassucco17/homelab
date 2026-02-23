# Secrets Reference

This document lists every secret required to operate the homelab, where each one is used,
and how to generate or obtain it.

---

## GitHub Repository Secrets

All secrets live at the repo level (Settings → Secrets and variables → Actions →
Repository secrets) and are shared between production and staging deployments.

| Secret | Description |
|--------|-------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale OAuth client ID for the GitHub Actions tag. Create under **Settings → OAuth clients** in the Tailscale admin console. |
| `TAILSCALE_OAUTH_SECRET` | Tailscale OAuth secret paired with the client ID above. |
| `SSH_PRIVATE_KEY` | Private key for SSH access to the server. The corresponding public key must be in `~/.ssh/authorized_keys` on the `deploy` user account. See [Dedicated deploy user](#dedicated-deploy-user). |
| `SERVER_SSH_HOST_KEY` | The server's SSH host key line as returned by `ssh-keyscan`. Used to pre-populate `known_hosts` so strict host-key checking is enforced. See [Obtaining the host key](#obtaining-the-host-key). |
| `SERVER_HOST` | Tailscale hostname or IP address of the server. |
| `TMDB_API_KEY` | API key for [The Movie Database (TMDB)](https://developer.themoviedb.org/). Used by the movie picker feature. Register at [themoviedb.org](https://www.themoviedb.org/settings/api). |
| `CLOUDFLARE_API_EMAIL` | Email address of the Cloudflare account. Cloudflare dashboard → Profile. |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token with **Zone:DNS:Edit** permission for `jamesmassucco.com`. Cloudflare dashboard → My Profile → API Tokens. |
| `GOOGLE_OAUTH2_CLIENT_ID` | Google OAuth 2.0 client ID. Google Cloud Console → APIs & Services → Credentials. |
| `GOOGLE_OAUTH2_CLIENT_SECRET` | Google OAuth 2.0 client secret. Google Cloud Console → APIs & Services → Credentials. |
| `GOOGLE_OAUTH2_COOKIE_SECRET` | 32-byte random secret for signing OAuth session cookies (used by both prod and staging). Generate with: `python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| `OAUTH2_AUTHORIZED_EMAILS` | Comma-separated Google email addresses allowed to log in. Set to your own Google account(s). |

---

## Actions variables

The following values are not sensitive and are stored as plain
[Actions variables](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables)
(Settings → Secrets and variables → Variables).

| Variable | Description | How to obtain |
|----------|-------------|---------------|
| `CLOUDFLARE_TRUSTED_IPS` | Comma-separated list of Cloudflare CDN IPv4 ranges | [Cloudflare IP ranges](https://www.cloudflare.com/ips/) — use the IPv4 list |
| `SERVER_USER` | SSH username — should be `deploy`, not `root`. See [Dedicated deploy user](#dedicated-deploy-user). | Set to `deploy` after completing the one-time server setup below. |

---

## Staging OAuth redirect URI

The staging OAuth proxy needs `https://oauth.staging.jamesmassucco.com/oauth2/callback`
added to the Google OAuth app's **Authorized Redirect URIs** (Google Cloud Console →
Credentials → the OAuth 2.0 Client ID → Edit).

---

## Obtaining the host key

Run the following on a trusted network (or directly on the server) and store the output
line as the `SERVER_SSH_HOST_KEY` repository secret:

```bash
ssh-keyscan -H <SERVER_HOST> 2>/dev/null
```

The output looks like:

```
|1|<hash>| ssh-ed25519 AAAA…
```

If the server is ever rebuilt and the host key changes, re-run `ssh-keyscan` and update
the secret.

---

## Dedicated deploy user

`SERVER_USER` should be a non-root `deploy` account on the server. Using `root` gives
an attacker who compromises the CI runner or the SSH key full server control. A
`deploy` user limits the blast radius to the homelab deployment itself.

One-time server setup:

```bash
# Create user and add to docker group
useradd -m -s /bin/bash deploy
usermod -aG docker deploy

# Allow write access to the deployment directory
mkdir -p /opt/homelab
chown -R deploy:deploy /opt/homelab

# Install the deploy SSH public key
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
echo "<deploy-public-key>" >> /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
```

Generate a dedicated key pair for the deploy user (do not reuse your personal SSH key):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f deploy_key
```

Store the private key (`deploy_key`) as the `SSH_PRIVATE_KEY` GitHub secret and copy the
public key (`deploy_key.pub`) to the server as shown above.
