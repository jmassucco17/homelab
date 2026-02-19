# Agent Guidance

This file provides guidance to Claude Code (and GitHub Copilot) agents interacting with this repo.

## Summary

This repo is primarily focused on deploying a public personal website at `jamesmassucco.com` and its sub-domains. The `networking/` directory contains core technologies (like `traefik` reverse proxy, oauth, and Cloudflare DDNS configuration) and other top-level directories contain containerized "services" which handle various pages within the site.

When creating a new module (i.e. a new page or new sub-site), make a new top-level folder and populate it with a `docker-compose.yml` and `start.sh`. Make sure to update `scripts/start_all.sh` to reference the new `start.sh`, update `networking/` to create a new sub-domain, and update `dependabot.yml` to ensure we track updates for the new docker image

## Details

### Setup

Run `bootstrap.sh` to fully initialize a new environment, including installing all necessary packages.

### Making changes

- Commit regularly during work, including during interactive sessions. Provide concise but informative commit messages
- Never commit to the `main` branch. If work is requested while on the `main` branch, checkout a new branch with a concise but informative name. When work is complete, or is ready for feedback, create a PR through GitHub

## Style Guide

### Python

- Import at the module level and access classes or functions as <module>.<func>; never import classes or functions directly
- Provide argument and return type hinting for all methods and functions
- Include docstrings for most classes and functions with brief description; in general, don't include args/returns info in the docstring unless it's non-obvious (e.g. if it returns a dict, describe the structure)
- Include comments for operations that need additional explanation
