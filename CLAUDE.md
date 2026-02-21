# Agent Guidance

This file provides guidance to Claude Code (and GitHub Copilot) agents interacting with this repo.

## Summary

This repo is primarily focused on deploying a public personal website at `jamesmassucco.com` and its sub-domains. The `networking/` directory contains core technologies (like `traefik` reverse proxy, oauth, and Cloudflare DDNS configuration) and other top-level directories contain containerized "services" which handle various pages within the site.

NOTE: From here on out, we'll refer to top-level directories that contain docker-based services, like `networking/`, `homepage`, etc., as "modules"

## Environment

- Run `bootstrap.sh` to fully initialize a new environment, including installing all necessary packages
- When adding a new package, add it to `requirements.txt` or `package.json` and then run `bootstrap.sh` to install
- If running `bootstrap.sh` does not install a package that you need to use, be sure to treat that as an issue and try to fix by updating either the requirements, or the `bootstrap.sh` script itself

## Modules

### Creating new modules

When creating a new module (i.e. a new subdomain):

1. **Create module directory** - Follow the pattern of either `homepage` (static/nginx) or `blog` (Python/FastAPI)
   - `Dockerfile`, `docker-compose.yml`, `docker-compose.local.yml`
   - Application code (`site/` for static, `app/` for Python)

2. **Update configuration files** - Look at how existing services are registered and follow the same pattern:
   - `scripts/start_local.sh` - Add to `ALL_SERVICES` and `LOCAL_HOSTS`
   - `networking/docker-compose.yml` - Add subdomain to cloudflare-ddns `DOMAINS`
   - `.github/dependabot.yml` - Add docker ecosystem entry
   - `.github/workflows/docker-integration.yml` - Add test job
   - `.github/workflows/build-and-push.yml` - Add matrix entry
   - `.github/workflows/deploy.yml` - Add input flag, file transfer, and deploy call
   - `homepage/site/index.html` - Add link in "Content and Projects"

### Listing all modules

Whenever modules are listed (e.g. in `deploy.yml`, or any other context), always use this order:

```
networking > shared-assets > homepage > and then the rest in alphabetical order
```

## Contributing

Follow all instructions in this section whenever you are contributing code to the repo

### Style Guides

- See `docs/style-guides/<language>` for language-specific style and usage
- If a language is not listed by name, use `other.md`
- These guides include usage information that should be followed whenever working with that language

### Reference Documents

The `docs/` directory contains reference documents that agents should load **only when relevant** to the current task:

- **`docs/deployments.md`** — Load when working on deployment workflows, CI pipelines, `start_service.sh`, or anything related to how services are built, tested, or shipped (CI integration tests, production deploy, staging deploy). Not needed for pure feature development inside a service.
- **`docs/secrets.md`** — Load when adding a new secret, modifying `networking/.env`, updating a workflow that reads secrets, or troubleshooting authentication/credentials issues. Not needed for routine code changes.

### Committing / Branches

- Never do work directly on the `main` branch
- If you are starting work and find yourself on the `main` branch, run `git switch -c <name-of-new-branch>` (come up with a reasonable and concise branch name, like `claude/restructure-docs`)
- When you create a new branch, always make sure that you complete some work, commit it (`git commit -m "<description of work>"`), and then run `gh pr create` to make a GitHub PR and push the code to GitHub
- When you are done with a body of work, always commit and then `git push -u origin HEAD`
