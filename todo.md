# TODO Items

## In progress

- Finish package based deployment, remove plan doc, and test for both local and prod deployments
- Move Traefik configuration from Docker labels to file-based config for better visibility

## New features/projects:

- Historical / future map viewer with ability to break down by city or state/country
- Mortgage calculator based on GSheet with ability to save locations, with common shared values that can be overridden for each property; if not overridden, it also keeps track of what the values were when you last viewed the item and shows you the changes
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for Python
- Add a knowledge base of some kind (i.e. personal Confluence or similar)

## Deployment improvements:

- Update secrets to use Vault
- Make better use of GHCR, or investigate alternative deployment management technologies (e.g. FluxCD)
- Learn how to use worktrees, and teach Claude how to do it
- Use narrower requirements at build time for modules, to speed up builds
- Make Tailscale remind me when Hetzner VPS is going to expire
- Database migration management (both at the schema layer and at the storage layer)
    - enable backup / restore capability
    - Fix -> time="2026-02-20T16:21:51Z" level=warning msg="volume \"travel-site_data-volume\" already exists but was created for project \"travel-site\" (expected \"travel\"). Use `external: true` to use an existing volume"

## Monitoring improvements

- Add Google OAuth to Grafana
- Create a custom dashboard for visualizing more specific metrics

## Organization

- Reduce sources of truth for what modules are available (listed in a lot of places, see #23 for example)
- Explain CSS strategy (have Copilot do this based on #24)

## Security

- Update Python to 3.13

## Bug fixes:

- Tailscale and NordVPN don't play nice together; fix it
- Snake is too wide on mobile

## Recurring Items

- Periodic usability review - go through all sections on both browser and mobile and make a list of usability critiques to fix
- Check for new Python version
- Check for new ruff version
- Check VPS for apt updates and OS updates

## Misc.

### Non-Python testing (future, requires new dependencies):

- **JS unit tests — theme-toggle.js**: Add Vitest + jsdom tests for `shared-assets/assets/scripts/theme-toggle.js` (cookie reading, `prefers-color-scheme`, toggle click, `data-theme` persistence). The function is already a clean ES module export so no refactor is needed.
- **JS unit tests — game logic**: Extract pure helpers from `snake.js` and `pong.js` IIFEs into separate `snake-logic.js` / `pong-logic.js` modules, then add Vitest tests for collision detection, speed scaling, and AI paddle clamping.


### High Priority (Quick Wins)
- Create shared utilities module for FastAPI boilerplate (app initialization, static files, Jinja2, health endpoints)
- Per-service requirements.txt or migrate to Poetry/uv for dependency management
- Consolidate all CSS into shared-assets (remove per-service CSS directories)

### Medium Priority (Architecture)
- Refactor travel modules to share code or merge into single app with sub-routers
- Add database migrations with Alembic
- Implement automated backup strategy for SQLite databases (rsync/rclone to S3/Backblaze)
- Add CI/CD deployment workflow (build/push images, deploy to production, smoke tests)
- Implement proper secret management (Docker Secrets, Vault, or managed service)

### Low Priority (Modernization)
- Evaluate HTMX for progressive enhancement or migrate to modern SSG/framework
- Consider PostgreSQL for production (keep SQLite for local dev)
- Migrate to Kubernetes (K3s) or Docker Swarm for orchestration
- Evaluate headless CMS for blog (Strapi, Payload, Directus)
- Switch to commercial geocoding API (Mapbox or Google Maps) for travel/maps
- Use Testcontainers for integration tests instead of custom GitHub Actions
- Consider Tailwind CSS instead of custom PostCSS architecture
- Upgrade from OAuth2-Proxy to Authelia or Authentik for better auth features
