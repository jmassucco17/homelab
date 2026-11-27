# TODO Items

## New features/projects:

- Replace travel-site with travel-maps, a site designed for creating annotated travel maps showing the destinations with brief descriptions / estimated visit dates
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for Python
- Add unit testing for FastAPI sites

## Brainstormed project ideas:

### New modules / subdomains

- **`recipes` subdomain** — A FastAPI app to store, tag, and search personal recipes. Support Markdown for instructions, ingredient lists, and photos. Could include a meal-planner view that generates a grocery list from selected recipes for the week.
- **`dashboard` subdomain** — A personal "new tab" page showing homelab container status, current weather (via OpenWeatherMap API), upcoming calendar events, and quick links. Think of it as a lightweight Heimdall/Homer, but custom-built and on-brand.
- **`habits` subdomain** — A daily habit tracker with a calendar/heatmap view (like GitHub's contribution graph). Store entries in a SQLite database via FastAPI. Simple login gate via the existing Google OAuth middleware.
- **`wiki` subdomain** — A self-hosted personal wiki / notes app. Could be as simple as a FastAPI-backed Markdown editor with file-system storage, or use an existing lightweight engine like Wiki.js or Outline. Good for capturing homelab runbooks, travel notes, and project docs.
- **`links` subdomain** — A personal bookmarks manager with tags, search, and a browser bookmarklet for quick-saving. Backend in FastAPI + SQLite. Alternative: deploy [Hoarder](https://github.com/hoarder-app/hoarder) (open-source, AI-assisted tagging).
- **`stats` subdomain** — A personal stats page that aggregates GitHub contribution data, Spotify listening history (via Last.fm scrobbles), Goodreads reading progress, and workout data. Displays charts powered by Chart.js or D3. A fun showcase of personal data without relying on third-party dashboards.
- **`now-playing` widget / subdomain** — A Spotify "Now Playing" integration, either as a widget embedded in the homepage or a dedicated minimal page. Uses the Spotify Web API with an OAuth refresh-token flow to display current track with album art.

### Expanding existing modules

- **Blog: RSS feed** — Add a `/feed.xml` route to the blog FastAPI app that generates a valid Atom/RSS feed from the Markdown posts. Already mentioned as a future goal in the 2025-05-01 blog post.
- **Blog: per-post pages + comments** — Render each blog post on its own URL (`/posts/<slug>`) and add a lightweight Giscus (GitHub Discussions-backed) comment widget. No backend changes needed for comments.
- **Games: daily Wordle clone** — Add a word-guessing game to the `games` module. Keep a word list in a JSON file; use the current date (seeded) to pick the day's word so all users share the same puzzle. Pure browser-side JS, no new backend routes needed.
- **Games: multiplayer Pong** — Add a WebSocket-backed real-time Pong game using FastAPI's WebSocket support. Two players share a room code; state is managed server-side. A fun excuse to learn WebSockets.
- **Travel: photo EXIF map** — Extend the travel module to auto-pin photos on the Leaflet map by reading GPS EXIF data embedded in uploaded images (using `pillow` / `piexif`). Eliminates manual coordinate entry.
- **Tools: URL shortener** — Add a `/shorten` route to the `tools` FastAPI app backed by SQLite. Serve short redirects from `tools.<domain>/s/<code>`. Useful for sharing personal links with a branded domain.
- **Tools: unit converter** — Add a lightweight unit-conversion page (length, weight, temperature, cooking measurements) to the tools module. Pure JavaScript on the frontend, no new backend routes needed.

### Infrastructure / homelab improvements

- **Kubernetes (k3s) migration** — Deploy [k3s](https://k3s.io/) on the Hetzner VPS and migrate one or two lightweight services to it. This satisfies the original learning goal from `2025-04-19.md` and sets the stage for multi-node expansion.
- **Self-hosted secrets manager** — Deploy [Infisical](https://infisical.com/) or [Vault](https://www.vaultproject.io/) in a new `secrets` module to replace the current GitHub-secrets-to-.env approach. Reduces secret sprawl as the number of modules grows.
- **Uptime / synthetic monitoring** — Add a Grafana Cloud synthetic monitoring probe (or self-hosted [Uptime Kuma](https://github.com/louislam/uptime-kuma)) that pings each public subdomain every minute and pages on downtime. Complement the existing node-exporter metrics.
- **Automated backups** — Write a cron job (or a scheduled GitHub Actions workflow) that dumps SQLite databases from all services, tarballs them, and pushes to Backblaze B2 or Cloudflare R2. Add a `restore` script. Currently there are no backups.
- **VPS auto-renewal reminder** — Create a GitHub Actions scheduled workflow that checks the Hetzner API for the VPS expiry date and sends an email/Slack notification 30 days out. Satisfies the `todo.md` item "Make Tailscale remind me when Hetzner VPS is going to expire."
- **Staging environment improvements** — Spin up a second cheap Hetzner VPS (or a local VM via Multipass) as a dedicated staging server that mirrors production. Automate the full deploy there on every PR merge to `main` before promoting to prod.

### AI / LLM ideas

- **Local LLM via Ollama** — Deploy [Ollama](https://ollama.com/) in a new `llm` module with a model like Llama 3 or Mistral. Expose a simple chat UI (Open WebUI works out-of-the-box with Ollama). Gate it behind Google OAuth. Great first step toward self-hosted AI.
- **AI-powered recipe suggestions** — Extend the `recipes` module with an endpoint that sends the current pantry contents (user-entered list) to the OpenAI API and returns recipe ideas. A low-effort way to add a practical LLM integration.
- **Blog post draft assistant** — Add an internal `/drafts` page (OAuth-protected) to the blog that lets you paste rough notes and calls the OpenAI API to generate a polished first draft in the same conversational style as existing posts.
- **Semantic blog search** — Store blog post embeddings (OpenAI or a local sentence-transformer model) in a vector store (e.g. ChromaDB) and add a `/search` route that returns semantically relevant posts for a free-text query.

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
