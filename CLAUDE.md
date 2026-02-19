# Agent Guidance

This file provides guidance to Claude Code (and GitHub Copilot) agents interacting with this repo.

## Summary

This repo is primarily focused on deploying a public personal website at `jamesmassucco.com` and its sub-domains. The `networking/` directory contains core technologies (like `traefik` reverse proxy, oauth, and Cloudflare DDNS configuration) and other top-level directories contain containerized "services" which handle various pages within the site.

When creating a new module (i.e. a new page or new sub-site), make a new top-level folder and populate it with a `docker-compose.yml` and `start.sh`. Make sure to:
- Update `scripts/start_all.sh` to reference the new `start.sh`
- Update `scripts/start_local.sh` to include the service in `ALL_SERVICES` and add its port to the help text
- Create a `docker-compose.local.yml` in the new module directory (see existing examples for the pattern)
- Update `networking/` to create a new sub-domain
- Update `dependabot.yml` to ensure we track updates for the new docker image

## Details

### Setup

Run `bootstrap.sh` to fully initialize a new environment, including installing all necessary packages. When adding a new package, add it to `requirements.txt` or `package.json` and then run `bootstrap.sh` to install

### Making changes

- Commit regularly during work, including during interactive sessions. Commit messages must be a single line - no multi-line messages, no body, no footers
- Never commit to the `main` branch. If work is requested while on the `main` branch, checkout a new branch with a concise but informative name. When work is complete, or is ready for feedback, create a PR through GitHub

## Style Guide

### Python

- Import at the module level and access classes or functions as <module>.<func>; never import classes or functions directly
- Provide argument and return type hinting for all methods and functions
- Include docstrings for most classes and functions with brief description; in general, don't include args/returns info in the docstring unless it's non-obvious (e.g. if it returns a dict, describe the structure)
- Include comments for operations that need additional explanation
- Use the `unittest` module when writing tests, but run them with `pytest` in command line
