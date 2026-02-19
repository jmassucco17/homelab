# TODO Items

## New features/projects:

- Replace travel-site with travel-maps, a site designed for creating annotated travel maps showing the destinations with brief descriptions / estimated visit dates
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for Python

## Testing improvements

- Call pytest with `-W error` to raise warnings as errors

## Deployment improvements:

- Teach Claude Code how to manage the deployment: how to ssh into the server, how to check the webpage from the public internet, how to run a local deployment, etc.
- Make Tailscale remind me when Hetzner VPS is going to expire
- Setup GitHub deployment checks of different site components

## Security

- Update Python to 3.13
- Don't use `root` for managing the VPS

## Bug fixes:

- Tailscale and NordVPN don't play nice together; fix it

## Recurring Items

- Check for new Python version
- Check for new ruff version
- Check VPS for apt updates and OS updates
