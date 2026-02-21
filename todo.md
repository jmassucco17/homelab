# TODO Items

## New features/projects:

- Replace travel-site with travel-maps, a site designed for creating annotated travel maps showing the destinations with brief descriptions / estimated visit dates
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for Python
- Add unit testing for FastAPI sites

## Non-Python testing (future, requires new dependencies):

- **JS unit tests — theme-toggle.js**: Add Vitest + jsdom tests for `shared-assets/assets/scripts/theme-toggle.js` (cookie reading, `prefers-color-scheme`, toggle click, `data-theme` persistence). The function is already a clean ES module export so no refactor is needed.
- **JS unit tests — game logic**: Extract pure helpers from `snake.js` and `pong.js` IIFEs into separate `snake-logic.js` / `pong-logic.js` modules, then add Vitest tests for collision detection, speed scaling, and AI paddle clamping.
- **Accessibility audits**: Run `@axe-core/cli` against each service's HTML in `docker-integration.yml` after containers are already running. Start with WCAG 2.1 level A, expand to level AA once baseline is green.

## Deployment improvements:

- Teach Claude Code how to manage the deployment: how to ssh into the server, how to check the webpage from the public internet, etc.
- Add a more standardized debug deployment (on local machine) and also teach claude how to use that
- Make Tailscale remind me when Hetzner VPS is going to expire
- Setup GitHub deployment checks of different site components

## Other AI-focused improvements:

- Set up a PR focused workflow and ensure Claude Code can use it, so that I can kick off tasks for it and then manage them through PRs
- Teach Claude how to run pre-commit hooks, how to check GitHub status, etc.
- Make Claude Code commit regularly during interactive sessions so that it's easy to roll back

## Bug fixes:

- Tailscale and NordVPN don't play nice together; fix it

## Recurring Items

- Check for new Python version
- Check for new ruff version
- Check VPS for apt updates and OS updates
