# Agent Guidance

This file provides guidance to Claude Code (and GitHub Copilot) agents interacting with this repo.

## Summary

This repo is primarily focused on deploying a public personal website at `jamesmassucco.com` and its sub-domains. The `networking/` directory contains core technologies (like `traefik` reverse proxy, oauth, and Cloudflare DDNS configuration) and other top-level directories contain containerized "services" which handle various pages within the site.

When creating a new module (i.e. a new page or new sub-site), make a new top-level folder and populate it with a `docker-compose.yml` and `start.sh`. Make sure to:

- Update `scripts/start_local.sh` to include the service in `ALL_SERVICES`
- Create a `docker-compose.local.yml` in the new module directory (see existing examples for the pattern)
- Update `networking/` to create a new sub-domain
- Update `dependabot.yml` to ensure we track updates for the new docker image
- Update `docker-integration.yml` to add integration tests for the new service
- Add an `image: ghcr.io/jmassucco17/homelab/<service>:latest` field to the service's `docker-compose.yml`
- Add a matrix entry to `.github/workflows/build-and-push.yml` following the standard service order

### Standard service order

Whenever services are listed (in `start_local.sh`, `deploy.yml`, `build-and-push.yml`, or any other context), always use this order:

```
networking > shared-assets > homepage > blog > travel > games
```

Networking is excluded from `build-and-push.yml` since it uses only pre-built upstream images.

## Details

### Setup

Run `bootstrap.sh` to fully initialize a new environment, including installing all necessary packages. When adding a new package, add it to `requirements.txt` or `package.json` and then run `bootstrap.sh` to install

### Making changes

- Commit regularly during work, including during interactive sessions. Commit messages must be a single line - no multi-line messages, no body, no footers
- Never commit to the `main` branch. If work is requested while on the `main` branch, checkout a new branch with a concise but informative name. When work is complete, or is ready for feedback, create a PR through GitHub

### Pre-commit checks

Before committing changes, run the following checks to ensure they will pass CI:

#### Linting (Python)

```bash
# Check for XXX comments (run from repo root on changed files)
git diff --name-only main...HEAD | xargs -r python scripts/check_xxx_comments.py

# Run Ruff linter and formatter
ruff check .
ruff format --check .

# Auto-fix issues where possible
ruff check --fix .
ruff format .
```

#### Type checking (Python)

```bash
# Run Pyright (requires npm packages installed)
npx pyright
```

#### Unit tests

```bash
# Run all tests with pytest
pytest -v

# Run tests for a specific module (e.g., travel)
cd travel && python -m unittest discover -s app -p "*_test.py"
```

#### Complete pre-commit workflow

```bash
# 1. Lint and format
ruff check --fix . && ruff format .

# 2. Run type checker
npx pyright

# 3. Run tests
pytest -v

# 4. If all pass, commit
git add . && git commit -m "Your commit message"
```

## Style Guide

### Python

- Import at the module level and access classes or functions as <module>.<func>; never import classes or functions directly
- Provide argument and return type hinting for all methods and functions
- Include docstrings for most classes and functions with brief description; in general, don't include args/returns info in the docstring unless it's non-obvious (e.g. if it returns a dict, describe the structure)
- Include comments for operations that need additional explanation
- Use the `unittest` module when writing tests, but run them with `pytest` in command line
- Tests should always be housed in the same directory as the file they test, and be named `<module>_test.py` (e.g. test for `main.py` should be `main_test.py`)
- Use modern type hints (`X | None` instead of `Optional[X]`)
- Use `datetime.now(UTC)` instead of deprecated `datetime.utcnow()`
- Whenever you create a new Python file, you must also create an associated `<module>_test.py` in the same directory

### Bash

- Make sure that new shell scripts (`.sh` files) have executable permissions (run `chmod +x <script>.sh`)
