# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

> _Spanish version: [README.es.md](./README.es.md)._

## Sales forecast model

- [`train_sales_forecast.py`](./train_sales_forecast.py) — Random Forest forecast of Nexova's monthly consolidated revenue (train 2016–2023, test 2024–2025). Docs, metrics and design choices: [`SALES_FORECAST.md`](./SALES_FORECAST.md). Run with `uv run python scripts/train_sales_forecast.py`.
