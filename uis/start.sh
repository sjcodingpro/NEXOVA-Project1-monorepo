#!/bin/sh
# /uis/start.sh
#
# Starts both frontends concurrently in the same container and forwards
# SIGTERM/SIGINT to both child processes -- without this, `docker
# compose down` would send SIGTERM to this script (PID 1), which would
# exit immediately while the two `npm run dev` subprocesses kept
# running until Docker's forced-kill timeout, rather than shutting down
# cleanly.
set -e

trap 'kill -TERM "$WEBSITE_PID" "$BACKOFFICE_PID" 2>/dev/null' TERM INT

# website's own "dev" script (npm run watch & npm run serve) already
# runs Tailwind's watcher and http-server bound to 0.0.0.0:3000 -- no
# extra flags needed here.
(cd /app/website && npm run dev) &
WEBSITE_PID=$!

# backoffice's "dev" script is bare `next dev`, with no port or host
# of its own -- both are passed through explicitly here. Without
# -H 0.0.0.0, Next's dev server binds to localhost only in some
# versions, which is unreachable from outside the container even with
# the port published; without -p 3001 it would default to 3000 and
# collide with website above.
(cd /app/backoffice && npm run dev -- -p 3001 -H 0.0.0.0) &
BACKOFFICE_PID=$!

wait "$WEBSITE_PID" "$BACKOFFICE_PID"
