import os

# Where the frontend is expected to send batches. The stub doesn't use it
# to redirect anything yet; it just establishes the env-var pattern so the
# real implementation can swap in without touching the frontend.
TELEMETRY_ENDPOINT = os.environ.get(
    "TELEMETRY_ENDPOINT", "http://localhost:8000/telemetry/events"
)
