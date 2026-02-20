# TODO Items

## New features/projects:

- Mortgage calculator based on GSheet with ability to save locations, with common shared values that can be overridden for each property; if not overridden, it also keeps track of what the values were when you last viewed the item and shows you the changes
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for Python

## Testing improvements

- Call pytest with `-W error` to raise warnings as errors
- Add non-python testing wherever appropriate

## Deployment improvements:

- Restructure the CI checks to have fewer top-level items (to make it easier to maintain the "required" checks list)
- Teach Claude Code how to manage the deployment: how to ssh into the server, how to check the webpage from the public internet, how to run a local deployment, etc.
- Make Tailscale remind me when Hetzner VPS is going to expire
- Setup GitHub deployment checks of different site components

## Organization

- Add instructions about port management for local deployments
- Reduce sources of truth for what packages are available (listed in a lot of places, see #23 for example)
- Consolidate `start.sh` scripts to just a single script that works for any package
- (add to CLAUDE.md) new subdomains should have a link from the homepage
- Explain CSS strategy (have Copilot do this based on #24)
- Apply a fixed order for all the subdomains wherever they appear (networking -> shared-assets -> homepage -> etc)
- Simplify the structure of travel maps / photos to just be a single site instead of two separate ones

## Security

- Update Python to 3.13
- Don't use `root` for managing the VPS

## Bug fixes:

- Tailscale and NordVPN don't play nice together; fix it
- Snake is too wide on mobile

## Recurring Items

- Check for new Python version
- Check for new ruff version
- Check VPS for apt updates and OS updates

## Misc.

- Update python deployment file to fix at 3.12
