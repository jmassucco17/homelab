# Python App On-Change Detection Plan

## Overview

The `build-and-deploy.yml` workflow already uses file-based on-change detection for
several modules (networking, portainer, monitoring, homepage, shared-assets). The four
Python-based services — `blog`, `travel`, `games`, and `tools` — currently always
build and deploy on every push to `main`, regardless of what changed. This plan
describes a heuristic for extending on-change detection to those services and discusses
whether file-based checks are sufficient for both Python apps and the existing
OTS / simple-container deployments.

---

## Heuristic for Python App Change Detection

### Shared dependencies

All four Python apps inherit from a common base image built from:

- `python-base/Dockerfile` — the `FROM python:3.12-slim` + pip-install layer
- `requirements.txt` — the single shared pip requirements file

A change to either of these files invalidates **every** Python app, because the base
image must be rebuilt and all apps that extend it must be re-built and re-deployed.

### Per-app source

Each app has its own source tree under its module directory (e.g. `blog/app/`,
`blog/Dockerfile`, etc.). A change there invalidates only that one app.

### Combined heuristic

For each Python service `<app>`, trigger a build+deploy if **any** of the following
changed in the commit:

```
requirements.txt
python-base/**
<app>/**
```

This means:

| Changed files          | blog | travel | games | tools |
| ---------------------- | ---- | ------ | ----- | ----- |
| `blog/app/main.py`     | ✓    |        |       |       |
| `travel/app/routes.py` |      | ✓      |       |       |
| `requirements.txt`     | ✓    | ✓      | ✓     | ✓     |
| `python-base/Dockerfile` | ✓  | ✓      | ✓     | ✓     |

### Implementation in `build-and-deploy.yml`

In the `setup` job's `check-changes` step, first test whether any shared Python
dependency changed, then OR that with the per-app directory check:

```bash
# Detect shared Python dependency changes once
python_base_changed=$(git diff --name-only HEAD^ HEAD \
  | grep -E "^(requirements\.txt|python-base/)" || true)

for module in blog travel games tools; do
  app_changed=$(git diff --name-only HEAD^ HEAD | grep "^${module}/" || true)
  if [ -n "$app_changed" ] || [ -n "$python_base_changed" ]; then
    echo "✓ ${module}: CHANGED"
    echo "${module}=true" >> "$GITHUB_OUTPUT"
  else
    echo "✗ ${module}: no changes"
    echo "${module}=false" >> "$GITHUB_OUTPUT"
  fi
done
```

Add corresponding outputs to the `setup` job:

```yaml
outputs:
  blog_changed:     ${{ steps.check-changes.outputs.blog }}
  travel_changed:   ${{ steps.check-changes.outputs.travel }}
  games_changed:    ${{ steps.check-changes.outputs.games }}
  tools_changed:    ${{ steps.check-changes.outputs.tools }}
```

Then use the same pattern as the existing simple/OTS services when invoking
`build-python` and `deploy-python`:

```yaml
blog: >-
  ${{ (github.event_name == 'push' && needs.setup.outputs.blog_changed == 'true')
   || (github.event_name == 'workflow_dispatch' && inputs.blog) }}
```

---

## Are File-Based Checks Sufficient?

### Python apps (blog, travel, games, tools)

**Strengths of file-based checks:**

- Simple to implement and easy to reason about.
- Directly maps "what changed in source" to "what needs to be deployed."
- Works perfectly for the common case: a single commit pushed to `main` after a PR
  merge (squash or merge commit).

**Weaknesses and edge cases:**

1. **`git diff HEAD^ HEAD` only sees the boundary of the last push.** If two commits
   are pushed at once and app-relevant files changed only in the first commit (not the
   last), the check will incorrectly report no change. In practice for this repo (solo
   developer, regular PR-merge workflow), this is not a real concern, but it is a
   theoretical gap.

2. **Force-push or history rewrite.** A force-push that rewrites `HEAD^` can confuse the
   diff. Again, this is unlikely in a disciplined solo workflow.

3. **Docker layer cache already handles redundant rebuilds gracefully.** Even if a
   false-positive triggers an unnecessary build, the Docker build cache means the
   rebuild is nearly instant and the resulting image is byte-for-byte identical. The
   cost of over-deploying is low.

4. **False negatives (missing a needed deploy) are worse than false positives.** The
   current "always deploy" approach avoids false negatives entirely. The file-based
   approach trades a small false-negative risk for a much shorter CI runtime on
   unrelated pushes.

**Verdict:** File-based checks are **sufficient** for this repo given the solo-developer,
single-commit-per-PR workflow. The heuristic above captures all realistic change
scenarios. If the team or commit frequency ever grows, consider a tag-based approach
(e.g. comparing image SHAs or using Docker layer digests) to make the decision more
robust.

**Alternative approach: image-digest comparison.** Build the image unconditionally on
every push, then compare the resulting image digest to the currently running digest.
Only re-deploy if the digest changed. This eliminates false negatives caused by
`git diff` limitations, at the cost of running every build step every time. For a
homelab with one developer, this is overkill; the file-based heuristic is the right
trade-off.

---

### OTS / simple containers

**OTS containers** (networking, portainer, monitoring): these use off-the-shelf Docker
Hub images. There is no custom build step — only a `docker compose pull && up`.

- File-based checks here detect changes to `docker-compose.yml`, `.env` templates, or
  other config files inside the module directory.
- This is entirely appropriate. The only reason to re-deploy an OTS container is if
  its configuration changed or its image tag (in `docker-compose.yml`) was bumped.
- Dependabot handles automatic image tag bumps in `docker-compose.yml`, so those
  changes will be committed as individual commits and detected normally.

**Simple (nginx-based) containers** (homepage, shared-assets): these have a custom
`Dockerfile` but no runtime dependencies outside their own directory. The existing
file-based check (detect changes in `homepage/` or `shared-assets/`) is fully
sufficient; there is no shared base image analogous to `python-base`.

**Verdict for OTS / simple containers:** The existing file-based checks are
**well-suited** to these service types. The only edge case worth noting is the same
`git diff HEAD^ HEAD` single-commit boundary issue described above — it applies equally
here but is equally unlikely to matter in practice.

---

## Summary

| Service type | Approach | Sufficient? |
| --- | --- | --- |
| OTS (networking, monitoring, portainer) | File diff on `<module>/` | ✓ Yes |
| Simple nginx (homepage, shared-assets) | File diff on `<module>/` | ✓ Yes |
| Python apps (blog, travel, games, tools) | File diff on `<module>/` OR `requirements.txt` OR `python-base/` | ✓ Yes, with shared-dep awareness |
