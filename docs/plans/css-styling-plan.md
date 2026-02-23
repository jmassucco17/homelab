# Website Styling Modernization Plan

## Current State

The site currently uses hand-crafted vanilla CSS spread across several locations:

| File | Purpose |
|------|---------|
| `shared-assets/assets/styles/main.css` | Shared design system — CSS custom properties (theme colors), typography, layout primitives (`.grid`, `.card`, `section`, `footer`) |
| `blog/app/static/styles/blog-index.css` | Blog listing page overrides |
| `blog/app/static/styles/blog-post.css` | Blog post typography, code blocks, animations |
| `travel-site/app/static/css/gallery.css` | Travel gallery layout (uses **hardcoded** colors — not on the design system) |
| `travel-site/app/static/css/map.css` | Travel map layout (also uses **hardcoded** colors) |
| `travel-site/app/static/css/admin.css` | Admin upload UI |

**Strengths of the current approach:**
- CSS custom properties already define a two-theme system (dark/light).
- Stylelint + Prettier enforces consistent formatting.
- `shared-assets` service acts as a CDN, so all sub-sites can pull the same base CSS.

**Pain points:**
- No CSS preprocessor means no nesting, no mixins, no partials — larger files are harder to maintain.
- `travel-site` CSS is completely disconnected from the design system (hardcoded hex values instead of `var(--color-*)` tokens).
- No consistent spacing / typography scale — values are chosen ad-hoc per file.
- No PostCSS pipeline, so modern CSS syntax (e.g. `color-mix()`, relative colors, nesting) is used inconsistently and not transpiled for older browsers.
- Linting is per-repo with no shared config between services.

---

## Inspiration Options

### Option A — Polished Terminal / Hacker (evolution of current dark theme)

The existing dark theme is already "cool tech" in vibe. Leaning further in that direction gives the site a distinctive, memorable identity that matches the homelab subject matter.

**References:**
- [terminal.shop](https://terminal.shop) — minimal, monospace, CLI-inspired
- [charm.sh](https://charm.sh) — neon-on-dark, polished CLI tools brand
- [htmx.org](https://htmx.org) — concise, dark, monospace heavy

**Design language:**
- Primary font: `Fira Code` (already in use) for headings and UI chrome
- Body text: `JetBrains Mono` or `IBM Plex Mono` for a slight upgrade
- Palette: deep navy/charcoal background, electric blue/cyan accent, subtle green for "ok" states
- Micro-animations: cursor blink on title, scanline overlay, typed-text hero
- Section dividers: ASCII-art style horizontal rules (`───────────────`)

**Pros:** Cohesive with the homelab theme; existing color tokens are close already.  
**Cons:** Monospace everywhere reduces readability in long-form blog posts.

---

### Option B — Clean Developer Portfolio (modern minimal)

Strips back to clean whitespace, strong typography hierarchy, and tasteful accents. Think a senior engineer's portfolio or a well-regarded technical blog.

**References:**
- [leerob.io](https://leerob.io) — minimal, fast, system fonts, subtle transitions
- [paco.me](https://paco.me) — ultra-minimal, strong type scale
- [rauno.me](https://rauno.me) — refined motion, high-contrast cards

**Design language:**
- Primary font: `Inter` (already loaded in `blog-post.css`) for headings and UI
- Body text: `Merriweather` (already loaded) for blog posts
- Palette: near-white background (#fafafa), near-black text, single mid-tone accent (indigo or teal)
- Components: thin borders, generous padding, sharp shadows on hover
- Dark mode: slightly warm dark (`#18181b`) instead of the current cold navy

**Pros:** Professional, readable, easy to extend; fonts are already loaded.  
**Cons:** Less distinctive — many portfolios look like this.

---

### Option C — Warm Editorial / Magazine

Warmer color palette inspired by high-quality editorial sites. Good fit if the travel blog becomes a first-class part of the site.

**References:**
- [every.to](https://every.to) — newsletter / editorial, great typography
- [increment.com](https://increment.com) — technical magazine aesthetic
- [narative.co](https://narative.co) — warm, photo-forward

**Design language:**
- Primary font: `Playfair Display` or `Libre Baskerville` for display headings
- Body text: `Source Serif 4` or `Georgia` for long-form reading
- Palette: cream/off-white background, warm brown/amber accents, dusty rose highlights
- Section dividers: thin horizontal rules with decorative fleurons
- Cards: photo-dominant with caption overlays rather than icon+text

**Pros:** Excellent for travel content; very readable long-form.  
**Cons:** Harder to make "dark mode" feel right; clashes with the hacker/tech vibe of the homelab content.

---

### Option D — Glassmorphism / Gradient (bold, contemporary)

High-contrast gradients, frosted-glass cards, and strong depth cues. Trending in 2024–2025 developer sites and SaaS landing pages.

**References:**
- [vercel.com](https://vercel.com) — gradient glows, sharp dark backgrounds
- [linear.app](https://linear.app) — gradient mesh hero, crisp cards
- [stripe.com](https://stripe.com) — frosted glass, layered depth

**Design language:**
- Background: deep dark with subtle gradient mesh or noise texture
- Cards: `backdrop-filter: blur()` frosted glass effect
- Accents: vivid gradient (purple→blue, or teal→cyan) on hero, CTAs, and borders
- Typography: `Geist` or `Plus Jakarta Sans` — clean geometric sans-serif
- Hover states: glow / neon border effect

**Pros:** Eye-catching and modern; very popular right now.  
**Cons:** Performance cost of `backdrop-filter`; can feel trendy/dated in two years.

---

## Technology Stack Options

### Option 1 — Vanilla CSS + PostCSS *(recommended for this project)*

Keep plain `.css` files but add a **PostCSS** build step to the `shared-assets` service. This unlocks:
- `postcss-nesting` — author CSS with the native nesting spec (`& .child {}`)
- `postcss-custom-media` — named breakpoints (`@media (--tablet) {}`)
- `autoprefixer` — vendor prefixes without manual effort
- `postcss-import` — merge `@import` statements into one minified bundle at build time

The output is still a plain CSS file served by Nginx — no JavaScript runtime required.

```
shared-assets/
  styles/
    base/
      _tokens.css      ← CSS custom properties (colors, spacing, type scale)
      _reset.css       ← minimal modern reset (no normalize.css bloat)
      _typography.css  ← font imports + base scale
    components/
      _buttons.css
      _cards.css
      _nav.css
    layout/
      _grid.css
      _page.css
    themes/
      _dark.css
      _light.css
    main.css           ← @import all partials → PostCSS builds this
```

**Tooling additions:** `postcss`, `postcss-cli`, `postcss-nesting`, `autoprefixer`  
**Build command:** `postcss styles/main.css -o dist/main.css`  
**Fits existing setup because:** Already has `npm`, `stylelint`, `prettier`. One new npm script and a `postcss.config.js`.

---

### Option 2 — SASS/SCSS

The classic CSS preprocessor. Adds variables, nesting, mixins, functions, `@use`/`@forward` module system.

**Pros:** Mature ecosystem; every CSS developer knows it; excellent IDE support.  
**Cons:** Adds a Dart Sass binary to the build; CSS variables (which are already used for theming) and SCSS variables serve overlapping purposes; the `dart-sass` package is 6 MB.

**Verdict:** SCSS makes most sense if you want powerful mixins for repetitive patterns. For this project's scale, PostCSS nesting and CSS variables cover the use case with less overhead.

---

### Option 3 — Tailwind CSS

Utility-first CSS framework. Write classes directly in HTML (`class="flex gap-4 p-6 rounded-lg"`).

**Pros:** Very fast to prototype; zero dead CSS in production (tree-shaking built in); excellent DX with the IntelliSense plugin.  
**Cons:** Jinja2 templates are not a first-class Tailwind target (works, but no HMR); HTML becomes verbose; harder to extract reusable component classes from `.jinja2` templates across multiple services; conflicts with the existing design-system approach.

**Verdict:** Better suited to React/Vue component libraries than server-rendered Jinja templates. Not recommended.

---

### Option 4 — Open Props + vanilla CSS

[Open Props](https://open-props.style) is a library of well-tuned CSS custom properties (spacing scale, color palette, type scale, easings, shadows). Drop it in as a CDN link and build on top of it.

**Pros:** Zero build step; plug-and-play design tokens; excellent dark mode support; very small (`~7 kB` for just the props you use).  
**Cons:** Adds a third-party CDN dependency; naming conventions differ from current `--color-*` tokens (migration required).

**Verdict:** Good option if the goal is a quick design system upgrade with zero build tooling. Can be combined with Option 1.

---

## Recommended Plan

**Recommended combination: Inspiration B or A + Technology Stack 1 (PostCSS)**

### Phase 1 — Consolidate the Design System

1. Refactor `shared-assets/assets/styles/main.css` into partials (`_tokens.css`, `_reset.css`, etc.) using the folder structure above.
2. Add PostCSS build step to `shared-assets` (new `npm run build:css` script and `Dockerfile` step).
3. Migrate `travel-site` CSS to use `var(--color-*)` tokens from the shared design system instead of hardcoded hex values.
4. Bump the `?v=` query string on CDN links to bust the cache.

### Phase 2 — Choose and Apply a Visual Refresh

5. Pick one of the inspiration options above (owner decision).
6. Update `_tokens.css` with the new color palette, spacing scale, and type scale.
7. Update fonts in `_typography.css`; remove unused Google Fonts imports.
8. Refine component styles (cards, buttons, nav) to match the chosen direction.

### Phase 3 — Per-Service Polish

9. Update `blog-post.css` typography to match the new scale.
10. Update travel-site `gallery.css` and `map.css` to use design tokens.
11. Verify dark/light theme toggle still works correctly with the new tokens.

### Phase 4 — Maintenance Improvements

12. Add `postcss-preset-env` to allow modern CSS syntax with a fallback target (e.g. `last 2 versions`).
13. Add a `lint:css` check to CI (currently linting exists but may not be wired into GitHub Actions).
14. Document the design token naming convention in `shared-assets/README.md`.
