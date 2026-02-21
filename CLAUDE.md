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

# XXX fix this section

When creating a new module (i.e. a new subdomain), make a new top-level folder and populate it with a `docker-compose.yml`. Make sure to:

- Update `scripts/start_local.sh` to include the service in `ALL_SERVICES`
- Create a `docker-compose.local.yml` in the new module directory (see existing examples for the pattern)
- Update `networking/` to create a new sub-domain
- Update `dependabot.yml` to ensure we track updates for the new docker image
- Update `docker-integration.yml` to add integration tests for the new service
- Add an `image: ghcr.io/jmassucco17/homelab/<service>:latest` field to the service's `docker-compose.yml`
- Add a matrix entry to `.github/workflows/build-and-push.yml` following the standard service order
- Add a link to the new service from the homepage (`homepage/site/index.html`) in the "Content and Projects" section

### Listing all modules

Whenever modules are listed (e.g. in `deploy.yml`, or any other context), always use this order:

```
networking > shared-assets > homepage > and then the rest in alphabetical order
```

## Contributing

### Style Guides

- See `docs/style-guides/<language>` for language-specific style and usage
- If a language is not listed by name, use `other.md`
- These guides include usage information that should be followed whenever working with that language

### Committing / Branches

- Commit regularly during work, including during interactive sessions. Commit messages must be a single line - no multi-line messages, no body, no footers
- Never commit to the `main` branch. If work is requested while on the `main` branch, checkout a new branch with a concise but informative name. When work is complete, or is ready for feedback, create a PR through GitHub
