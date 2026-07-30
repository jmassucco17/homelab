# Deployment Strategy Improvement Plan

## Overview

This document reviews the current deployment strategy and proposes concrete improvements
in two areas: **continuous deployment** (making deploys faster, safer, and more automated)
and **deployment visibility** (knowing exactly what is deployed, when it was deployed, and
by whom).

---

## Current State

### What works well

- Push to `main` automatically triggers build + deploy for all services (basic CD).
- `workflow_dispatch` supports selective per-service deploys and a staging environment.
- `_deploy.yml` is a single reusable workflow called by `build-and-deploy.yml`, keeping
  logic in one place.
- Pre-built images are pulled from GHCR; the server never needs to build anything.
- Staging environment mirrors production using `docker-compose.staging.yml` overlays.

### Gaps

| Gap | Impact |
|-----|--------|
| Every push to `main` deploys **all** services, even unchanged ones | Slow deploys; unnecessary risk from redeploying healthy services |
| No automated rollback if a deploy fails | A broken deploy stays broken until someone notices and manually redeploys |
| No GitHub Environments or approval gates | Any push to `main` immediately goes to production with no human review step |
| No persistent deployment history | Knowing what was deployed when requires digging through GitHub Actions run history |
| No "what's running" record on the server | No easy way to see which commit is live without checking GHCR or GitHub |
| No deployment event correlation with metrics | Grafana shows a spike — was it from the deploy 10 minutes ago? Unknown |
| No deploy notifications | Silent success and silent failures unless someone watches the Actions tab |

---

## Improvement 1 — Change-based selective deployment (High impact, Medium effort)

### Problem

On every push to `main`, all services are redeployed even if only one was modified. This:

- Unnecessarily restarts healthy services with no code change.
- Makes deploys slower (7+ service restarts when 1 is needed).
- Increases the blast radius: a bad `docker-compose.yml` in an unrelated service can
  block the whole deploy.

### Proposed change

Use `git diff` to detect which service directories changed between the previous commit and
HEAD. Pass those results as the per-service boolean flags into `_deploy.yml`.

**Implementation:**

Add a `detect-changes` job to `build-and-deploy.yml` (runs only on `push` to `main`):

```yaml
detect-changes:
  runs-on: ubuntu-latest
  outputs:
    networking: ${{ steps.changes.outputs.networking }}
    shared-assets: ${{ steps.changes.outputs.shared-assets }}
    homepage: ${{ steps.changes.outputs.homepage }}
    blog: ${{ steps.changes.outputs.blog }}
    games: ${{ steps.changes.outputs.games }}
    tools: ${{ steps.changes.outputs.tools }}
    travel: ${{ steps.changes.outputs.travel }}
    monitoring: ${{ steps.changes.outputs.monitoring }}
  steps:
    - uses: actions/checkout@v6
      with:
        fetch-depth: 2
    - id: changes
      run: |
        for svc in networking shared-assets homepage blog games tools travel monitoring; do
          if git diff --name-only HEAD~1 HEAD | grep -q "^${svc}/\|^scripts/\|^python-base/"; then
            echo "${svc}=true" >> "$GITHUB_OUTPUT"
          else
            echo "${svc}=false" >> "$GITHUB_OUTPUT"
          fi
        done
```

Changes to `scripts/` and `python-base/` always trigger all dependent services (since
they are cross-cutting). Changes to `.github/` do not trigger a deploy on their own.

**On `workflow_dispatch`:** keep the current behaviour — all checkboxes default to `true`
and the operator decides what to deploy. Change detection is only applied on push.

**Files affected:** `.github/workflows/build-and-deploy.yml`

---

## Improvement 2 — Automated rollback on deploy failure (High impact, Medium effort)

### Problem

If `start_service.sh` exits non-zero (e.g. a service fails its Docker healthcheck),
`_deploy.yml` marks the run as failed and stops. The broken service stays broken until
someone manually redeploys.

### Proposed change

Add a rollback step that fires `on: failure` in the deploy job. It uses `git` to find the
previous successful deploy commit and triggers another run against that SHA's image tag.

**Implementation options (ordered by effort):**

**Option A — Re-deploy the previous `latest` image (Low effort)**

Keep a `latest-prev` tag in GHCR that the build job rotates on every successful build:
before pushing a new `latest`, re-tag the current `latest` as `latest-prev`. The rollback
step runs a second SSH command that calls `start_service.sh` with `IMAGE_TAG=latest-prev`.

```yaml
- name: Rollback on failure
  if: failure()
  env:
    SERVER_USER: ${{ vars.SERVER_USER }}
    SERVER_HOST: ${{ secrets.SERVER_HOST }}
  run: |
    ssh -i ~/.ssh/deploy_key "${SERVER_USER}@${SERVER_HOST}" \
      "IMAGE_TAG=latest-prev /opt/homelab/scripts/start_service.sh <failed-service>"
```

Requires: `_build.yml` rotates `latest-prev` before pushing `latest`.

**Option B — Notify and gate (Low effort, higher visibility)**

Instead of auto-rolling back, emit a failure notification (see Improvement 5) and
require a human to trigger a `workflow_dispatch` rollback. This avoids the risk of an
auto-rollback that also fails (e.g. if the underlying issue is infrastructure-related).

**Recommendation:** Implement Option B first (it is low-effort and avoids compounding
failures), then graduate to Option A once `latest-prev` tagging is in place.

**Files affected:** `.github/workflows/_deploy.yml`, `.github/workflows/_build.yml`

---

## Improvement 3 — GitHub Environments with deployment protection rules (High impact, Medium effort)

### Problem

All secrets are repo-level and any push to `main` deploys to production immediately.
There is no approval gate, no audit trail scoped to "this run used prod credentials",
and no protection against accidental deploys.

### Proposed change

Create GitHub Environments (`prod` and `staging`) under **Settings → Environments** and:

1. Declare `environment: ${{ inputs.environment }}` on the `deploy` job in `_deploy.yml`.
2. Add a **required reviewer** protection rule to `prod` so that push-triggered deploys
   require a human to approve before the job runs.
3. Move environment-specific secrets into their respective environment (complementary to
   the secrets-management plan).

**Benefits beyond secret scoping:**

- GitHub automatically records a deployment entry with status (success/failure), commit
  SHA, and timestamp in the **Environments** tab of the repository. This gives persistent
  visibility for free (see Improvement 4).
- The deployment is visible in pull request timelines (when a branch was staged/deployed).
- The `prod` protection rule acts as a "last mile" safety net even on unreviewed direct
  pushes.

**Files affected:** `.github/workflows/_deploy.yml`  
**Manual steps:** Create `prod` and `staging` environments in GitHub Settings.

---

## Improvement 4 — Deployment history via GitHub Deployments API (Medium impact, Low effort)

### Problem

There is no persistent, queryable record of what was deployed, when, and whether it
succeeded. GitHub Actions run history is the only source of truth, but it is noisy (CI
runs, lint runs, etc.) and does not show what version is currently live.

### Proposed change

Once GitHub Environments are set up (Improvement 3), GitHub automatically creates a
deployment record for each run that uses an `environment:` key. No additional API calls
are needed for basic history.

For richer records, add an explicit deployment status step using `actions/github-script`:

```yaml
- name: Create deployment record
  uses: actions/github-script@v7
  with:
    script: |
      const deployment = await github.rest.repos.createDeployment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        ref: context.sha,
        environment: '${{ inputs.environment }}',
        description: 'Deployed by ${{ github.actor }}',
        auto_merge: false,
        required_contexts: [],
      });
      core.setOutput('deployment_id', deployment.data.id);

- name: Update deployment status
  if: always()
  env:
    JOB_STATUS: ${{ job.status }}
  uses: actions/github-script@v7
  with:
    script: |
      await github.rest.repos.createDeploymentStatus({
        owner: context.repo.owner,
        repo: context.repo.repo,
        deployment_id: ${{ steps.create-deployment.outputs.deployment_id }},
        state: process.env.JOB_STATUS === 'success' ? 'success' : 'failure',
        environment_url: 'https://jamesmassucco.com',
        description: 'Commit ${{ github.sha }}',
      });
```

The Environments tab on the repository then shows:

```
prod   ● Active   sha-abc1234   deployed 2 hours ago by jmassucco17
                  sha-def5678   deployed 3 days ago by jmassucco17
```

**Files affected:** `.github/workflows/_deploy.yml`

---

## Improvement 5 — Deploy version file on the server (Low impact, Low effort)

### Problem

After a deploy there is no easy way to answer "what commit is running right now?" from
the server itself (without checking GHCR or GitHub).

### Proposed change

Add a step to the remote SSH block in `_deploy.yml` that writes a `DEPLOY_INFO` file to
`/opt/homelab/`:

```bash
cat > /opt/homelab/DEPLOY_INFO <<EOF
commit=${COMMIT_SHA}
deployed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
deployed_by=${DEPLOYER}
environment=${ENVIRONMENT}
EOF
```

Pass `COMMIT_SHA=${{ github.sha }}` and `DEPLOYER=${{ github.actor }}` as environment
variables in the SSH step.

This file can also be served by any service (e.g. homepage) at a `/_version` endpoint,
making the running version visible without SSH access.

**Files affected:** `.github/workflows/_deploy.yml`

---

## Improvement 6 — Grafana Cloud deployment annotations (Medium impact, Low effort)

### Problem

When Grafana shows a metric spike or log burst, there is no visual marker to correlate
it with a deployment. You have to cross-reference GitHub Actions timestamps manually.

### Proposed change

After each successful deploy, post an annotation to Grafana Cloud using its HTTP API:

```yaml
- name: Post deployment annotation to Grafana
  if: success() && inputs.environment == 'prod'
  env:
    GRAFANA_CLOUD_API_KEY: ${{ secrets.GRAFANA_CLOUD_API_KEY }}
    GRAFANA_CLOUD_ORG_SLUG: ${{ secrets.GRAFANA_CLOUD_ORG_SLUG }}
  run: |
    curl -s -X POST \
      "https://grafana.com/api/orgs/${GRAFANA_CLOUD_ORG_SLUG}/annotations" \
      -H "Authorization: Bearer ${GRAFANA_CLOUD_API_KEY}" \
      -H "Content-Type: application/json" \
      -d '{
        "text": "Deploy: ${{ github.sha }} by ${{ github.actor }}",
        "tags": ["deploy", "prod"]
      }'
```

Annotations appear as vertical lines on Grafana dashboards so metric changes can be
instantly correlated with deployments.

Requires: monitoring module deployed (see `monitoring-plan.md`), and one additional
secret: `GRAFANA_CLOUD_ORG_SLUG` (the Grafana Cloud organization slug, visible in the
Grafana Cloud URL).

**Files affected:** `.github/workflows/_deploy.yml`

---

## Improvement 7 — Deploy notifications (Low impact, Low effort)

### Problem

Deployments succeed or fail silently. The only way to know is to watch the Actions tab.

### Proposed change

Add a notification step that fires `if: always()` at the end of the deploy job. The
simplest implementation uses a GitHub Actions summary and a webhook:

**Option A — GitHub Actions job summary (zero new dependencies):**

```yaml
- name: Write deploy summary
  if: always()
  run: |
    echo "## Deployment Summary" >> "$GITHUB_STEP_SUMMARY"
    echo "| Field | Value |" >> "$GITHUB_STEP_SUMMARY"
    echo "|-------|-------|" >> "$GITHUB_STEP_SUMMARY"
    echo "| Environment | ${{ inputs.environment }} |" >> "$GITHUB_STEP_SUMMARY"
    echo "| Commit | \`${{ github.sha }}\` |" >> "$GITHUB_STEP_SUMMARY"
    echo "| Actor | ${{ github.actor }} |" >> "$GITHUB_STEP_SUMMARY"
    echo "| Status | ${{ job.status }} |" >> "$GITHUB_STEP_SUMMARY"
```

This writes a formatted summary to the GitHub Actions run page — visible at a glance
without reading individual step logs.

**Option B — Webhook (e.g. Discord/ntfy):**

Store the webhook URL as a secret (`DEPLOY_WEBHOOK_URL`) and POST a JSON payload.
Useful if the homelab owner wants push notifications on a phone.

**Files affected:** `.github/workflows/_deploy.yml`

---

## Summary Table

| # | Improvement | CD or Visibility | Impact | Effort |
|---|-------------|-----------------|--------|--------|
| 1 | Change-based selective deployment | CD | High | Medium |
| 2 | Automated rollback on failure | CD | High | Medium |
| 3 | GitHub Environments + protection rules | Both | High | Medium |
| 4 | Deployment history via GitHub Deployments API | Visibility | Medium | Low |
| 5 | Deploy version file on server | Visibility | Low | Low |
| 6 | Grafana Cloud deployment annotations | Visibility | Medium | Low |
| 7 | Deploy notifications (summary / webhook) | Visibility | Low | Low |

**Recommended order of implementation:** 3 → 4 → 7 → 1 → 5 → 6 → 2

Start with GitHub Environments (3) because it unlocks the Deployments API (4) for free
and lays the groundwork for environment-scoped secrets (cross-referenced in
`secrets-management-plan.md`). Add the job summary notification (7) as a free win.
Change detection (1) and the version file (5) can follow as a second pass. Grafana
annotations (6) depend on the monitoring module from `monitoring-plan.md`. Rollback (2)
is last because it requires `latest-prev` image tagging and carries the most complexity.

---

## Implementation Checklist

### Phase 1 — Visibility foundations

- [ ] Create `prod` and `staging` GitHub Environments in repository Settings
- [ ] Add `environment: ${{ inputs.environment }}` to the `deploy` job in `_deploy.yml`
- [ ] Add `actions/github-script` deployment + deployment-status steps to `_deploy.yml`
- [ ] Add job summary notification step to `_deploy.yml`

### Phase 2 — Continuous deployment improvements

- [ ] Add `detect-changes` job to `build-and-deploy.yml` for push-triggered deploys
- [ ] Wire change-detection outputs into the `deploy` job's per-service inputs
- [ ] Add `DEPLOY_INFO` file write to the SSH block in `_deploy.yml`

### Phase 3 — Monitoring integration and rollback

- [ ] Add Grafana Cloud annotation step to `_deploy.yml` (requires monitoring module)
- [ ] Rotate `latest-prev` tag in `_build.yml` before pushing new `latest`
- [ ] Add rollback step (`if: failure()`) to `_deploy.yml` using `latest-prev`

### Manual steps (not in the repo)

- [ ] Create `prod` GitHub Environment with required reviewer protection rule
- [ ] Create `staging` GitHub Environment (no protection rule needed)
- [ ] Move environment-specific secrets into their respective environments (see `secrets-management-plan.md`)
- [ ] Add `GRAFANA_CLOUD_ORG_SLUG` secret (if implementing Improvement 6)
- [ ] Add `DEPLOY_WEBHOOK_URL` secret (if implementing Option B of Improvement 7)
