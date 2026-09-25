# /uis/Dockerfile
#
# Serves both frontends from a single container:
#   - website:    a static HTML/Tailwind site (NOT Next.js) served via
#                 http-server, per uis/website/package.json's own
#                 "dev": "npm run watch & npm run serve" script
#   - backoffice: a genuine Next.js app, served via `next dev`
#
# This deliberately diverges from the ticket's "install dependencies
# for /uis/website and /uis/backoffice, both Next.js apps" framing --
# website is a static site with its own Tailwind build/watch step, not
# a second Next.js instance. Both apps are still installed and started
# independently, from the same container, on separate ports, which is
# the actual requirement underneath that framing.

FROM node:20-alpine

WORKDIR /app

# Installed separately, in their own subdirectories, so each app's own
# lockfile governs its own install -- these are two independent
# projects, not a shared workspace.
COPY website/package.json website/package-lock.json* ./website/
RUN cd website && npm install

COPY backoffice/package.json backoffice/package-lock.json* ./backoffice/
RUN cd backoffice && npm install

COPY website/ ./website/
COPY backoffice/ ./backoffice/

# website's Tailwind watcher performs an initial compile as soon as it
# starts, but building once here too means styles.css exists and is
# correct from the very first request, not just after the watcher's
# first pass completes.
RUN cd website && npm run build

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# website: 3000 (http-server, hardcoded in website's own "serve"
#          script -- see start.sh)
# backoffice: 3001 (passed explicitly in start.sh, since backoffice's
#          own "dev" script is bare `next dev` with no port of its own)
EXPOSE 3000 3001

CMD ["/app/start.sh"]
