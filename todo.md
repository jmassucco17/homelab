New features/projects:

- Replace travel-site with travel-maps, a site designed for creating annotated travel maps showing the destinations with brief descriptions / estimated visit dates
- Change blog so that we don't need to generate HTML for each post, and instead just need the raw markdown
- New project (TBD) that requires creating an iOS app
- Setup nice colored logging for python

Deployment improvements:

- Add tooling (maybe outside this repo) to automatically monitor homepage, blog, and other public websites and email me if they go down
- Teach Claude Code how to manage the deployment: how to ssh into the server, how to check the webpage from the public internet, etc.
- Add a more standardized debug deployment (on local machine) and also teach claude how to use that
- Make Tailscale remind me when Hetzner VPS is going to expire

Other AI-focused improvements:

- Set up a PR focused workflow and ensure Claude Code can use it, so that I can kick off tasks for it and then manage them through PRs
- Teach Claude how to run pre-commit hooks, how to check Github status, etc.
- Make Claude Code commit regularly during interactive sessions so that it's easy to roll back
- Teach Claude how to add packages (both python and npm)

Bug fixes:

- Tailscale and NordVPN don't play nice together; fix it
- Github checks consistently failing (pyright)
