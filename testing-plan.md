# Non-Python Testing Plan

The Python side of the codebase has solid coverage: pytest unit tests, Ruff
linting, Pyright type checking, and docker integration tests that exercise every
HTTP endpoint.  The non-Python parts — shell scripts, JavaScript, CSS, HTML
templates, Docker Compose files, and GitHub Actions workflows — have no
automated quality checks beyond a couple of pre-commit hooks.  This document
proposes concrete additions in rough priority order.

---

## 1. CSS linting in CI (zero new dependencies)

**What:** Run `npm run lint:css` (stylelint) as a GitHub Actions job.

**Why it is missing:** `stylelint` is already installed and configured in
`.stylelintrc.json` + `package.json`, but the `linting.yml` workflow only covers
Python (Ruff, Pyright).  The pre-commit hook is not enforced in CI so CSS
problems only get caught locally.

**Suggested change:** Add a `lint-css` job to `.github/workflows/linting.yml`
that runs when any `*.css` file changes:

```yaml
lint-css:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Install npm dependencies
      run: npm ci
    - name: Run stylelint
      run: npm run lint:css
```

**Coverage:** All CSS files under `shared-assets/`, `blog/`, `travel/`, and
`games/`.

---

## 2. ShellCheck static analysis for shell scripts

**What:** Run `shellcheck` against every `*.sh` file in CI.

**Why it matters:** The four shell scripts (`bootstrap.sh`,
`scripts/start_local.sh`, `scripts/start_service.sh`, `travel/start.sh`) contain
error-handling logic, argument parsing, and `docker compose` orchestration.
ShellCheck is a mature static analyser that catches common pitfalls (unquoted
variables, SC2086/SC2206 array expansion bugs, missing `|| true` guards, etc.)
without requiring tests to be written.

**Suggested change:** Add a `shellcheck` job to `linting.yml`:

```yaml
shellcheck:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Install ShellCheck
      run: sudo apt-get install -y shellcheck
    - name: Run ShellCheck
      run: find . -name '*.sh' -not -path './node_modules/*' | xargs shellcheck
```

**Coverage:** All shell scripts in the repo.

---

## 3. Prettier HTML check in CI

**What:** Run `npx prettier --check '**/*.html'` (and optionally `**/*.jinja2`)
as a CI job.

**Why it is missing:** Prettier with `prettier-plugin-jinja-template` is already
installed and configured (`.prettierrc`), and there is a pre-commit hook that
auto-formats HTML.  However there is no CI check that enforces formatting — so
PRs that bypass pre-commit can land with inconsistently formatted templates.

**Suggested change:** Add a `prettier` job to `linting.yml` that fails when
files are not already formatted:

```yaml
prettier:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Install npm dependencies
      run: npm ci
    - name: Check HTML formatting
      run: npx prettier --check '**/*.html' '**/*.jinja2'
```

---

## 4. actionlint for GitHub Actions workflow validation

**What:** Run `actionlint` against every workflow file under `.github/workflows/`.

**Why it matters:** GitHub Actions YAML has its own schema — invalid `uses:`
references, wrong context variables (`github.event.pull_request.base.sha` used
in a push event, for example), and typos in step outputs all fail silently or
produce confusing runtime errors.  `actionlint` catches these at lint time.

**Suggested change:** Add an `actionlint` job to `linting.yml`:

```yaml
actionlint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Run actionlint
      uses: rhysd/actionlint@v1
```

**Coverage:** All five workflow files + two custom actions under `.github/`.

---

## 5. Docker Compose configuration validation

**What:** Run `docker compose config` (without starting containers) for every
`docker-compose.yml` in CI.

**Why it matters:** A malformed Compose file or a missing required environment
variable can break deployment silently.  `docker compose config` validates the
file against the Compose spec and resolves variable substitution.  It is already
implicitly tested for the services exercised in `docker-integration.yml`, but
the networking service is only partially tested (only three of its four services
are started), and none of the `docker-compose.local.yml` files are validated at
all.

**Suggested change:** Add a `compose-validate` job to `docker-integration.yml`:

```yaml
compose-validate:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Create networking/.env stub
      run: |
        cat > networking/.env <<'EOF'
        CLOUDFLARE_API_EMAIL=test@example.com
        CLOUDFLARE_API_TOKEN=test-token
        CLOUDFLARE_TRUSTED_IPS=0.0.0.0/0
        GOOGLE_OAUTH2_CLIENT_ID=test-client-id
        GOOGLE_OAUTH2_CLIENT_SECRET=test-client-secret
        GOOGLE_OAUTH2_COOKIE_SECRET=0000000000000000000000000000000000000000000000000000000000000000
        OAUTH2_AUTHORIZED_EMAILS=test@example.com
        EOF
    - name: Validate all Compose files
      run: |
        for dir in networking shared-assets homepage blog travel games; do
          echo "--- $dir ---"
          docker compose -f "$dir/docker-compose.yml" config --quiet
          docker compose -f "$dir/docker-compose.yml" \
                         -f "$dir/docker-compose.local.yml" config --quiet
        done
```

---

## 6. JavaScript unit tests for `theme-toggle.js`

**What:** Add a small Vitest (or Jest) test suite for
`shared-assets/assets/scripts/theme-toggle.js`.

**Why it is a good candidate:** It is the only JavaScript file that is a proper
ES module with an exported function (`insertThemeToggle`).  Its logic — reading
the `theme` cookie, respecting `prefers-color-scheme`, toggling `data-theme` on
`<html>`, and persisting the choice — can be unit-tested in a DOM emulation
environment (jsdom) without a browser.

**Suggested test cases:**
- When no cookie is set and the system prefers dark, `data-theme` is set to
  `"dark"` on `documentElement`.
- When no cookie is set and the system prefers light, `data-theme` is set to
  `"light"`.
- When a `theme=light` cookie already exists, `data-theme` is set to `"light"`
  regardless of `prefers-color-scheme`.
- Clicking the toggle button flips `data-theme` between `dark` and `light`.
- After a click, the updated theme is written back to `document.cookie`.
- If the container element does not exist, the function returns without throwing
  (the `console.warn` path).

**Tooling:** Vitest is the most natural choice here because the project already
uses `npm` and PostCSS; it has built-in jsdom support with zero configuration.
Add `vitest` as a dev dependency and a `test` script to `package.json`.

---

## 7. Snake and Pong game logic unit tests

**What:** Extract the pure-logic helper functions from `snake.js` and `pong.js`
into a testable module, then add unit tests.

**Why it is harder:** Both files are written as immediately-invoked function
expressions (IIFEs) that directly reference DOM elements and `localStorage` at
the top level, so they cannot currently be imported in a test environment without
a lot of setup.

**Suggested refactor (minimal):** Move the side-effect-free helpers into a
named export in a separate file:

- `snake-logic.js` — exports `intervalMs(score)`, `checkWallCollision(head,
  cols, rows)`, `checkSelfCollision(head, snake)`, and
  `spawnFood(snake, cols, rows)` (deterministic version accepting a random seed
  or mock).
- `pong-logic.js` — exports `clampPaddle(y, canvasH, paddleH)`,
  `ballHitsPaddle(ball, paddle)`, and `aiPaddleTarget(ballY, paddleY, speed)`.

**Suggested test cases for snake:**
- `intervalMs(0)` returns `BASE_INTERVAL_MS` (150 ms).
- `intervalMs(score)` decreases by `SPEED_DELTA` every `SPEED_STEP` points.
- `intervalMs(large_score)` never returns less than `MIN_INTERVAL_MS` (60 ms).
- `checkWallCollision` detects all four wall boundaries.
- `checkSelfCollision` returns true when the head matches any body segment.
- `spawnFood` never places food on an occupied cell.

**Note:** This item requires a small refactor before tests can be written.  The
refactor should be done at the same time as the tests are added.

---

## 8. Accessibility audit in integration tests

**What:** Run `axe-core` (or `pa11y`) against the HTML served by each running
container in `docker-integration.yml`.

**Why it matters:** The existing integration tests confirm that HTML is returned,
but they do not check that the HTML is accessible.  Catching a missing `alt`
attribute, improper heading order, or missing `aria-label` in CI prevents
regressions.

**Suggested approach:** After the `Test index endpoint returns HTML` step in each
service job, add an axe scan using the `axe-core` CLI:

```yaml
- name: Install axe-cli
  run: npm install -g @axe-core/cli
- name: Run accessibility audit
  run: |
    SERVICE_IP=$(docker inspect <service> --format='{{.NetworkSettings.IPAddress}}')
    axe "http://${SERVICE_IP}:8000/" --exit
```

`--exit` causes a non-zero exit code when violations are found, failing the CI
step.

**Starting scope:** Target only WCAG 2.1 level A violations to keep the initial
bar achievable, then expand to level AA once the baseline is green.

---

## Summary table

| Area | Tooling | New dependency? | Effort |
|---|---|---|---|
| CSS linting in CI | stylelint (already installed) | No | Low |
| Shell script linting | shellcheck | No (available via apt) | Low |
| HTML formatting in CI | prettier (already installed) | No | Low |
| GitHub Actions validation | actionlint | No (GitHub Action) | Low |
| Compose file validation | docker compose config | No | Low |
| JS unit tests — theme-toggle | Vitest + jsdom | Yes (vitest) | Medium |
| JS unit tests — game logic | Vitest + logic extraction | Yes (vitest + refactor) | Medium |
| Accessibility audits | axe-core CLI | Yes (@axe-core/cli) | Medium |
