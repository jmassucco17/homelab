# Shared Assets

This service hosts CSS, scripts, and icons served as a CDN at `https://assets.jamesmassucco.com`.
Other site modules reference it via `<link href="https://assets.jamesmassucco.com/styles/main.css?v=X.Y">`.

## CSS Architecture

Styles use a **PostCSS** build pipeline. Source partials live in `assets/styles/src/`:

| File | Purpose |
|------|---------|
| `src/_tokens.css` | CSS custom properties — Vercel-inspired design tokens (colors, fonts, radii) |
| `src/_reset.css` | Minimal CSS reset |
| `src/_typography.css` | Font imports (Inter, Fira Code) and base text styles |
| `src/_layout.css` | Body, sections, grid, footer |
| `src/_components.css` | Cards, navigation link, theme toggle |

`main.src.css` imports all partials; `main.css` is the built output served to browsers.

### Building CSS

After editing any partial, rebuild the output file:

```bash
npm run build:css
```

Commit **both** the source partials and the built `main.css`.

### Bumping the cache-busting version

When you deploy updated CSS, increment the `?v=` query string in every HTML file that links to `main.css`:

```
grep -r "main.css?v=" . --include="*.html" --include="*.jinja2"
```

## Development Caching

In local dev (`scripts/start_local.sh`), the `docker-compose.local.yml` mounts `nginx.local.conf`
which sets `Cache-Control: no-store` for **all** assets. This means every browser reload fetches
the latest files with no caching — no need to hard-refresh or disable DevTools caching manually.

Production uses the standard `nginx.conf` with:
- Long-lived cache (`1y, immutable`) for content-hashed filenames (e.g. `file.abc123.css`)
- Short-lived cache (`1s, must-revalidate`) for other CSS/JS — forces a revalidation every second
