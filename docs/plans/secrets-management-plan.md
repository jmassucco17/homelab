# Secrets Management Improvement Plan

## Overview

This document reviews the current approach to managing secrets in this repo
(`docs/secrets.md` + `_deploy.yml`) and proposes concrete improvements ranked by
security impact and implementation cost.

---

## Current State

### How secrets are stored today

All secrets live as **repository-level** GitHub Actions secrets (Settings → Secrets and
variables → Actions). There is no use of GitHub Environments.

| Secret | Scope | Notes |
|--------|-------|-------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Repo | Shared by prod and staging |
| `TAILSCALE_OAUTH_SECRET` | Repo | Shared by prod and staging |
| `SSH_PRIVATE_KEY` | Repo | Shared by prod and staging |
| `SERVER_HOST` | Repo | Shared by prod and staging |
| `SERVER_USER` | Repo | Shared by prod and staging |
| `NETWORKING_ENV` | Repo | Full contents of `networking/.env` for **prod** |
| `STAGING_NETWORKING_ENV` | Repo | Full contents of `networking/.env` for **staging** |
| `TMDB_API_KEY` | Repo | Prod only (conditional in workflow) |

### How secrets are used in `_deploy.yml`

1. **`NETWORKING_ENV` / `STAGING_NETWORKING_ENV`** — Written to `networking/.env` via:
   ```yaml
   run: |
     printf '%s' "${{ secrets.NETWORKING_ENV }}" > networking/.env
   ```
2. **`TMDB_API_KEY`** — Written to `tools/.env` via:
   ```yaml
   run: printf 'TMDB_API_KEY=%s\n' "${{ secrets.TMDB_API_KEY }}" > tools/.env
   ```
3. **`SSH_PRIVATE_KEY`** — Written to `~/.ssh/deploy_key`, then used by `ssh` and `scp`.
4. **`SERVER_HOST` / `SERVER_USER`** — Interpolated directly into shell strings:
   ```yaml
   run: ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no \
     "${{ secrets.SERVER_USER }}@${{ secrets.SERVER_HOST }}" ...
   ```

---

## Problems Identified

### Problem 1 — Direct `${{ secrets.X }}` interpolation into shell commands (High)

GitHub Actions substitutes `${{ secrets.X }}` by embedding the raw secret value into
the YAML/shell text **before** the shell runner sees it. This means:

- If a secret value contains characters meaningful to the shell (quotes, `$`, backticks,
  newlines), the shell command can be **malformed or broken**. For example, if
  `NETWORKING_ENV` contains a double-quote, the `printf` call in `_deploy.yml` will
  fail or behave unexpectedly because it is surrounded by `"…"` in the YAML `run:` block.
- The secret value is embedded in the step's command string, which is more visible
  (though GitHub does mask known secret values in logs, this relies on exact string
  matching and can miss multiline secrets or truncated values).

**Affected steps in `_deploy.yml`:**
- `Write networking/.env from secret` — `printf '%s' "${{ secrets.NETWORKING_ENV }}"`
- `Write tools/.env from secret` — `printf 'TMDB_API_KEY=%s\n' "${{ secrets.TMDB_API_KEY }}"`
- `Upload archive to server` — `"${{ secrets.SERVER_USER }}@${{ secrets.SERVER_HOST }}"`
- `Deploy services on server` — same `SERVER_USER@SERVER_HOST` interpolation
- `Set up SSH key` — `"${{ secrets.SERVER_HOST }}"` passed to `ssh-keyscan`

The fix is to pass secrets through the `env:` block and reference them as shell
environment variables (`$VAR` instead of `${{ secrets.VAR }}`):

```yaml
- name: Write networking/.env from secret
  env:
    NETWORKING_ENV: ${{ secrets.NETWORKING_ENV }}
  run: printf '%s' "$NETWORKING_ENV" > networking/.env
```

This is shell-safe because the variable is evaluated by the shell, not embedded in the
script text.

---

### Problem 2 — Monolithic `.env` blobs are hard to rotate and audit (Medium)

Storing the entire `networking/.env` as a single opaque GitHub secret means:

- **Rotating one credential** (e.g. the Cloudflare API token) requires fetching the
  current blob out of band, editing it, and re-uploading the entire thing. There is no
  UI affordance for "update just this field."
- **Auditing changes** is impossible — GitHub's secret update history only records
  *when* a secret was updated, not what changed inside it.
- The format of the blob must stay in sync with the fields that `docker-compose.yml`
  expects, but this constraint is invisible when editing the secret in the GitHub UI.

---

### Problem 3 — No GitHub Environments; no deployment protection rules (Medium)

All secrets are repo-level. Any workflow job that runs can read any secret regardless of
whether it is deploying to production or staging. This means:

- There is no gate that requires a human to approve a production deployment before it
  proceeds — any push to `main` immediately deploys to prod with no review step.
- There is no distinction in the audit log between "this run used prod secrets" and
  "this run used staging secrets."
- The separate `NETWORKING_ENV` / `STAGING_NETWORKING_ENV` naming convention is a
  manual workaround for the absence of environment-scoped secrets. When both environments
  have their own secret named `NETWORKING_ENV`, the conditional logic in the workflow
  (`if staging … else …`) goes away.

---

### Problem 4 — `StrictHostKeyChecking=no` bypasses host-key verification (Medium)

`_deploy.yml` runs `ssh-keyscan` to pre-populate `~/.ssh/known_hosts`, then immediately
passes `-o StrictHostKeyChecking=no` to both `scp` and `ssh`. The flag makes the
`known_hosts` population pointless — if the host key has been replaced (e.g. via a
MITM or server rebuild), the connection proceeds anyway.

`ssh-keyscan` is also a TOFU (Trust On First Use) approach: it trusts whatever key the
server returns at scan time, providing no guarantee of authenticity against a compromised
network path.

---

### Problem 5 — SSH key and target user are not scoped to a deploy role (Low)

`docs/secrets.md` documents `SERVER_USER` as "typically `root` or a deploy user" without
enforcing a non-root choice. An SSH key that logs in as `root` has unrestricted access
to the server; a compromised CI runner or leaked key would allow full server takeover.

---

## Proposed Improvements

The items below are ordered from highest-impact / lowest-effort to lowest-impact / highest
effort.

---

### Improvement 1 — Pass all secrets via `env:` blocks (High impact, Low effort)

**Change:** In every `run:` step in `_deploy.yml` that currently uses
`${{ secrets.X }}` inside the shell script text, move the secret to an `env:` key on
that step and reference it as `$VAR_NAME`.

**Example — before:**
```yaml
- name: Write tools/.env from secret
  run: printf 'TMDB_API_KEY=%s\n' "${{ secrets.TMDB_API_KEY }}" > tools/.env
```

**Example — after:**
```yaml
- name: Write tools/.env from secret
  env:
    TMDB_API_KEY: ${{ secrets.TMDB_API_KEY }}
  run: printf 'TMDB_API_KEY=%s\n' "$TMDB_API_KEY" > tools/.env
```

Apply the same change to the SSH host/user references and the `ssh-keyscan` call.

**Files affected:** `.github/workflows/_deploy.yml`

---

### Improvement 2 — Adopt GitHub Environments with environment-scoped secrets (High impact, Medium effort)

**Change:** Create two GitHub Environments (`prod` and `staging`) under **Settings →
Environments** in the repository, then:

1. Move `NETWORKING_ENV` into the `prod` environment, renamed to `NETWORKING_ENV`.
2. Move `STAGING_NETWORKING_ENV` into the `staging` environment, also named
   `NETWORKING_ENV` (same name, different scope).
3. Move `TMDB_API_KEY` into the `prod` environment (it is only used for prod).
4. Leave the Tailscale and SSH secrets at the repo level since they are shared, **or**
   duplicate them into both environments for tighter scoping.
5. In `_deploy.yml`, declare `environment: ${{ inputs.environment }}` on the `deploy`
   job. GitHub will automatically supply the right `NETWORKING_ENV` for the chosen
   environment — the `if staging … else …` conditional in the "Write networking/.env"
   step can be removed entirely.
6. Add a **required reviewer** protection rule to the `prod` environment so that any
   production deployment (including automatic pushes to `main`) requires manual approval.

**Before (workflow):**
```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Write networking/.env from secret
        run: |
          if [ "${{ inputs.environment }}" = "staging" ]; then
            printf '%s' "${{ secrets.STAGING_NETWORKING_ENV }}" > networking/.env
          else
            printf '%s' "${{ secrets.NETWORKING_ENV }}" > networking/.env
          fi
```

**After (workflow):**
```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - name: Write networking/.env from secret
        env:
          NETWORKING_ENV: ${{ secrets.NETWORKING_ENV }}
        run: printf '%s' "$NETWORKING_ENV" > networking/.env
```

**Files affected:** `.github/workflows/_deploy.yml`, `.github/workflows/build-and-deploy.yml`

---

### Improvement 3 — Break up the monolithic `NETWORKING_ENV` blob into individual secrets (Medium impact, Medium effort)

**Change:** Replace the single `NETWORKING_ENV` blob with one GitHub secret per
`.env` variable. The `_deploy.yml` step then assembles `networking/.env` from the
individual secrets at deploy time:

```yaml
- name: Write networking/.env
  env:
    CLOUDFLARE_API_EMAIL: ${{ secrets.CLOUDFLARE_API_EMAIL }}
    CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    CLOUDFLARE_TRUSTED_IPS: ${{ secrets.CLOUDFLARE_TRUSTED_IPS }}
    GOOGLE_OAUTH2_CLIENT_ID: ${{ secrets.GOOGLE_OAUTH2_CLIENT_ID }}
    GOOGLE_OAUTH2_CLIENT_SECRET: ${{ secrets.GOOGLE_OAUTH2_CLIENT_SECRET }}
    GOOGLE_OAUTH2_COOKIE_SECRET: ${{ secrets.GOOGLE_OAUTH2_COOKIE_SECRET }}
    OAUTH2_AUTHORIZED_EMAILS: ${{ secrets.OAUTH2_AUTHORIZED_EMAILS }}
  run: |
    cat > networking/.env <<EOF
    CLOUDFLARE_API_EMAIL=${CLOUDFLARE_API_EMAIL}
    CLOUDFLARE_API_TOKEN=${CLOUDFLARE_API_TOKEN}
    CLOUDFLARE_TRUSTED_IPS=${CLOUDFLARE_TRUSTED_IPS}
    GOOGLE_OAUTH2_CLIENT_ID=${GOOGLE_OAUTH2_CLIENT_ID}
    GOOGLE_OAUTH2_CLIENT_SECRET=${GOOGLE_OAUTH2_CLIENT_SECRET}
    GOOGLE_OAUTH2_COOKIE_SECRET=${GOOGLE_OAUTH2_COOKIE_SECRET}
    OAUTH2_AUTHORIZED_EMAILS=${OAUTH2_AUTHORIZED_EMAILS}
    EOF
```

Benefits:
- Rotating the Cloudflare token only requires updating `CLOUDFLARE_API_TOKEN`.
- The set of required secrets is visible and enumerated in the workflow YAML, not hidden
  inside an opaque blob.
- Adding a new `.env` field means adding a new secret and a new line in the workflow —
  both changes are visible in code review.

Downside: more secrets to configure initially (one-time setup cost).

**Note:** `CLOUDFLARE_TRUSTED_IPS` is a list of IP ranges and contains no sensitive
data. It could alternatively be stored as a plain (non-secret) **Actions variable**
(Settings → Secrets and variables → Variables tab) or directly in the repo config.

**Files affected:** `.github/workflows/_deploy.yml`, `docs/secrets.md`

---

### Improvement 4 — Store the server's SSH host key fingerprint as a secret (Medium impact, Low effort)

**Change:** Instead of running `ssh-keyscan` (which trusts whatever the server returns
at scan time) and then overriding it with `-o StrictHostKeyChecking=no`, store the
server's known-good SSH host key as a GitHub secret (`SERVER_SSH_HOST_KEY`) and use it
to populate `known_hosts`:

```yaml
- name: Set up SSH key
  env:
    SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
    SERVER_SSH_HOST_KEY: ${{ secrets.SERVER_SSH_HOST_KEY }}
    SERVER_HOST: ${{ secrets.SERVER_HOST }}
  run: |
    mkdir -p ~/.ssh
    printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/deploy_key
    chmod 600 ~/.ssh/deploy_key
    printf '%s\n' "$SERVER_SSH_HOST_KEY" >> ~/.ssh/known_hosts
```

Then remove `-o StrictHostKeyChecking=no` from all `ssh` and `scp` calls. With a
pinned host key in `known_hosts`, strict checking is both safe and meaningful.

To obtain the value of `SERVER_SSH_HOST_KEY`, run on the server:
```bash
ssh-keyscan -H <server-host> 2>/dev/null
```
and store the output line (e.g. `|1|…| ssh-ed25519 AAAA…`) as the secret. If the
server is ever rebuilt and the host key changes, update the secret to match.

**Files affected:** `.github/workflows/_deploy.yml`, `docs/secrets.md`

---

### Improvement 5 — Use a dedicated, non-root deploy user (Low impact, Medium effort)

**Change:** Create a `deploy` user on the server with:
- Write access to `/opt/homelab`
- Membership in the `docker` group (to run `docker compose`)
- No other elevated permissions (no `sudo`, no `root` shell)

Update `SERVER_USER` to `deploy` and document this requirement in `docs/secrets.md`.

This limits the blast radius of a compromised CI runner or leaked SSH key: an attacker
can update the homelab deployment but cannot run arbitrary root commands.

**Files affected:** `docs/secrets.md` (documentation only; server setup is manual)

---

## Summary Table

| # | Improvement | Security impact | Effort | Removes issue |
|---|-------------|----------------|--------|---------------|
| 1 | Pass secrets via `env:` blocks | High | Low | Problem 1 |
| 2 | GitHub Environments + protection rules | High | Medium | Problem 3 |
| 3 | Individual secrets per `.env` field | Medium | Medium | Problem 2 |
| 4 | Pinned SSH host key in `known_hosts` | Medium | Low | Problem 4 |
| 5 | Dedicated non-root deploy user | Low | Medium | Problem 5 |

**Recommended order of implementation:** 1 → 4 → 2 → 3 → 5

Items 1 and 4 are pure workflow changes with no GitHub UI setup required and can be done
in a single PR. Item 2 requires creating Environments in GitHub settings before the
workflow change can be merged. Items 3 and 5 can follow as separate PRs.
