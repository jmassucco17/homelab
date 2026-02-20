# Docker Registry Deployment Plan

## Current Deployment Approach

Every deployment follows this flow:

1. GitHub Actions creates a `.tar.gz` archive of the entire repository (source code,
   templates, static assets, config files, etc.)
2. The archive is uploaded to the VPS via `scp` over a Tailscale tunnel (~whole-repo
   transfer every time)
3. An SSH session extracts the archive into `/opt/homelab`
4. Each requested service's `start.sh` runs `docker compose up -d --build --wait`,
   which **builds the Docker image on the production server**

### Pain Points

- **Builds happen on the production server** — the VPS spends CPU/RAM compiling Python
  wheels and assembling image layers while the site is live.
- **Entire repo is transferred every run** — even a one-line change to `blog/` transfers
  all of `travel/`, `games/`, `shared-assets/`, etc.
- **No versioned images** — there is no record of which image is currently running;
  rolling back requires re-deploying from a prior commit.
- **Reproducibility gap** — CI tests run `--build` in GitHub Actions and the exact same
  `--build` runs again on the server; subtle differences (network, cache state, pip
  index) could produce different images.
- **Long cold-start deploys** — a fresh server (or one with a pruned image cache) must
  download all base layers **and** build all images before traffic is served.

---

## Proposed Approach: GitHub Container Registry (GHCR)

### How It Works

1. **CI builds and pushes images** — a new `build-and-push` workflow (or additional
   steps in the existing `docker-integration.yml`) builds each service's Docker image
   and pushes it to `ghcr.io/jmassucco17/homelab/<service>:<git-sha>` and also tags it
   `:latest`.
2. **Each `docker-compose.yml` gains an `image:` field** — pointing to the GHCR image,
   e.g. `image: ghcr.io/jmassucco17/homelab/blog:latest`.  The `build:` block can stay
   as a fallback for local development.
3. **Deploy becomes a pull-and-run** — the deploy workflow SSHs into the server and
   runs `docker compose pull && docker compose up -d --wait`.  No archive, no build
   step on the server.
4. **Config files are transferred separately** — only the small set of files that vary
   between environments (docker-compose overrides, `.env` secrets) needs to reach the
   server.  This can be done with a targeted `scp` of a few kilobytes instead of the
   full archive.

### Local Development

Local developers continue to use `--build` via `docker-compose.local.yml` overrides.
Optionally, the local workflow can also pull the latest pre-built image from GHCR
(`docker compose pull`) to skip re-building unchanged layers.

---

## Benefits

| Benefit | Detail |
|---------|--------|
| **No build on production** | VPS only pulls and starts containers — no compiler, no pip, no layer assembly during live traffic |
| **Reproducible deploys** | The exact image tested in CI is what runs in production — byte-for-byte identical |
| **Faster deployments** | `docker pull` fetches only changed layers; subsequent deploys are much faster than rebuilding from scratch |
| **Smaller transfer** | Config files are kilobytes; the full-archive SCP step is eliminated |
| **Easy rollbacks** | `docker compose up -d --no-deps blog` with an older tag reverts a service in seconds |
| **Image history** | GHCR stores every pushed image tagged with the git SHA, giving a complete audit trail |
| **Parallel CI builds** | Each service can be built as a separate job with full layer caching (`actions/cache` + `--cache-from`) |
| **Reduced server attack surface** | The server no longer needs build tools or the repo source — only Docker and compose |
| **Watchtower-compatible** | A registry-based setup is a prerequisite for tools like Watchtower that auto-pull updated images |

---

## Downsides

| Downside | Mitigation |
|----------|-----------|
| **Registry dependency** | GHCR is GitHub-managed and highly available; the server could cache the last pulled image and fall back to it if the registry is unreachable |
| **Authentication on server** | The VPS needs a GitHub Personal Access Token (or deploy token) to pull private images; this is a one-time `docker login` stored in `/root/.docker/config.json` |
| **Config still needs to reach server** | A small targeted `scp` of compose files and `.env` replaces the full-archive SCP; adds a small amount of workflow logic |
| **Image size / bandwidth** | Base layers are cached after the first pull; only delta layers are transferred on subsequent deploys |
| **CI build time** | Each push now runs `docker build + push`; mitigated by `--cache-from` which reuses unchanged layers from the previous push |
| **Tag management** | Need a strategy for tagging (`:latest`, `:<sha>`, `:<semver>`); `:latest` is simplest to start and can be refined later |
| **GHCR public/private** | Images from a public repo are public by default; for a personal site this is fine, but worth noting |

---

## Alternative Approaches

### Option A — Self-Hosted Registry

Run `registry:2` (the official Docker image) on the VPS itself.

**Pros:** No external dependency; no authentication over the internet; images stay on the same machine.  
**Cons:** The registry is on the production server — if the server is down, CI cannot push; adds another service to maintain; no web UI by default (Harbor adds one but is heavy).

**Verdict:** Overkill for a single-server homelab; GHCR is simpler to operate.

---

### Option B — Watchtower (Auto-Pull on Image Push)

Keep CI push to GHCR, but instead of a deploy SSH step, run Watchtower on the server.
Watchtower polls GHCR and automatically restarts containers when a new `:latest` image
is available.

**Pros:** Zero-touch deployments after initial setup; no SSH deploy step needed.  
**Cons:** Less control over *when* a deploy happens; harder to do selective per-service deploys; rollbacks require pushing a previous image tag; the polling interval introduces deploy lag (typically 30–300 s); not appropriate for coordinated multi-service deploys (e.g. networking must start before apps).

**Verdict:** Appealing for simple setups; the existing selective-deploy workflow dispatch
(individual service checkboxes) would be harder to replicate with Watchtower.

---

### Option C — Git Pull on Server (No Registry)

Instead of SCP-ing an archive, SSH into the server and run `git pull`, then
`docker compose up -d --build`.

**Pros:** No registry required; simple; the server always has the full source history.  
**Cons:** Still builds on production; the server needs git credentials; image reproducibility is not guaranteed; build time on VPS is unchanged.

**Verdict:** Eliminates the archive transfer but keeps the core problem (building on production).

---

### Option D — Pre-Built Archives With Image Tarballs

Build images in CI, export them with `docker save`, include the tarballs in the archive,
and `docker load` on the server.

**Pros:** No registry required; images are reproducible.  
**Cons:** Image tarballs are very large (100 MB–1 GB each); SCP becomes much slower; no layer deduplication between services; awkward to manage.

**Verdict:** Worse than the current approach in every measurable dimension; not recommended.

---

## Recommended Implementation Plan

### Phase 1 — Add image tags to compose files

1. Add `image: ghcr.io/jmassucco17/homelab/<service>:latest` to each `docker-compose.yml`
   (keep the existing `build:` block as a local fallback).
2. Add `image: ghcr.io/jmassucco17/homelab/<service>:local` to each
   `docker-compose.local.yml` so local builds are tagged consistently.

### Phase 2 — CI build-and-push workflow

3. Create `.github/workflows/build-and-push.yml` that triggers on push to `main`.
4. For each service, add a job that:
   - Logs in to GHCR with `docker/login-action`
   - Builds the image with `docker/build-push-action` using `cache-from: type=gha`
     and `cache-to: type=gha,mode=max`
   - Tags as `:latest` and `:<git-sha>` and pushes both

### Phase 3 — Update deploy workflow

5. Replace the "Create deployment archive" and "Upload archive to server" steps with a
   targeted `scp` that transfers only:
   - `docker-compose.yml` for each service being deployed
   - `networking/.env`
6. Replace the remote `./start.sh` call with:
   ```bash
   docker login ghcr.io -u USERNAME --password-stdin <<< "$GHCR_TOKEN"
   docker compose pull
   docker compose up -d --wait
   ```
7. Add `GHCR_TOKEN` (a GitHub PAT with `read:packages` scope) as a repository secret.

### Phase 4 — Rollback tooling (optional)

8. Update `deploy.yml` workflow dispatch inputs to include an optional `image_tag`
   parameter that defaults to `latest` but can be overridden with a git SHA to roll
   back any service to a previous build.
