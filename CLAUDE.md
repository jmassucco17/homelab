# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Organization/Architecture

- The `networking/` directory houses the traefik reverse proxy and other core networking aspects of the site
- Other folders like `homepage/` and `blog/` house pages which can be deployed, and which rely on `networking/` components to be accessible and secure
- `scripts/` contains automations for deployments and for checking the repo
- `bootstrap.sh` is used to provision a new repo

### Key Patterns

- Each service has its own `Dockerfile`, `docker-compose.yml`, and `start.sh` script
- Services use the `web` Docker network for internal communication
- Traefik handles routing and SSL with automatic Let's Encrypt certificates
- Python services use FastAPI with SQLAlchemy for database operations
- Authentication uses OAuth2 with selective protection (public/admin routes)

### Database Architecture

- travel-site uses dual database sessions:
  - Read-only sessions for public routes
  - Full access sessions for admin routes
- Database models defined in `database.py` files

### Static Site Generation

- Blog uses markdown frontmatter + Jinja2 templates
- Assets are shared via the shared-assets service
- RSS feed automatically generated

## Commands

- `scripts/deploy.sh` - Deploy to production server
- `scripts/start_all.sh` - Deploy locally for testing
- `ruff format; ruff check` - Lint python code

### Testing

- For Python: Use pytest with `pytest travel-site/app/database_test.py` or similar paths
- Tests are typically in `*_test.py` files alongside source code

## Style Guide

### Python

- Import at the module level and access classes or functions as <module>.<func>; never import classes or functions directly
- Provide argument and return type hinting for all methods and functions
- Include docstrings for most classes and functions with brief description; in general, don't include args/returns info in the docstring unless it's non-obvious (e.g. if it returns a dict, describe the structrue)
- Include comments for operations that need additional explanation
