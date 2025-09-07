# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development & Testing

- `npm run lint:css` - Lint CSS files using stylelint
- `npm run lint:types` - Run Python type checking with pyright
- `ruff format` - Format Python code (configured in pyproject.toml)
- `ruff check` - Lint Python code

### Local Development

- `scripts/start_all.sh` - Start all services locally with Docker Compose
- `blog/generate_blog.py` - Generate static blog HTML from markdown posts
- `scripts/deploy.sh` - Deploy to production server (requires .env configuration)

### Testing

- For Python: Use pytest with `pytest travel-site/app/database_test.py` or similar paths
- Tests are typically in `*_test.py` files alongside source code

## Architecture

This is a homelab project consisting of multiple containerized web services:

### Service Structure

- **networking/** - Traefik reverse proxy with SSL termination
- **shared-assets/** - Common static assets (CSS, JS, icons) served across services
- **homepage/** - Static homepage at jamesmassucco.com
- **blog/** - Static blog generator (Python + Jinja2) at blog.jamesmassucco.com
- **travel-site/** - FastAPI app with OAuth2 authentication at travel.jamesmassucco.com

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

### Deployment

- Production deployment via `scripts/deploy.sh`
- Uses tar archive with .gitignore exclusions
- Services start automatically via systemd or Docker restart policies

## Style Guide

### Python

- Import at the module level and access classes or functions as <module>.<func>; never import classes or functions directly
- Provide argument and return type hinting for all methods and functions
