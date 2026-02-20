# TODO Items

## New features/projects:

- Export google maps history into travel maps
- Mortgage calculator based on GSheet with ability to save locations, with common shared values that can be overridden for each property; if not overridden, it also keeps track of what the values were when you last viewed the item and shows you the changes
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for Python

## Testing improvements

- Add non-python testing wherever appropriate

## Deployment improvements:

- Finish package based deployment, remove plan doc, and test for both local and prod deployments
- Setup a proper staging environment that both me and AI agents can interact with, for testing major changes in a full environment (need to figure out domain structure)
- Teach Claude Code how to manage the deployment: how to ssh into the server, how to check the webpage from the public internet, how to run a local deployment, etc.
- Make Tailscale remind me when Hetzner VPS is going to expire
- Database migration management (both at the schema layer and at the storage layer)
    - enable backup / restore capability
    - Fix -> time="2026-02-20T16:21:51Z" level=warning msg="volume \"travel-site_data-volume\" already exists but was created for project \"travel-site\" (expected \"travel\"). Use `external: true` to use an existing volume"


## Organization

- Add instructions about port management for local deployments
- Reduce sources of truth for what packages are available (listed in a lot of places, see #23 for example)
- Explain CSS strategy (have Copilot do this based on #24)
- Apply a fixed order for all the subdomains wherever they appear (networking -> shared-assets -> homepage -> others in alphabetical order)

## Security

- Update Python to 3.13
- Don't use `root` for managing the VPS

## Bug fixes:

- Tailscale and NordVPN don't play nice together; fix it
- Snake is too wide on mobile

## Recurring Items

- Periodic usability review - go through all sections on both browser and mobile and make a list of usability critiques to fix
- Check for new Python version
- Check for new ruff version
- Check VPS for apt updates and OS updates

## Misc.

- Update python deployment file to fix at 3.12
