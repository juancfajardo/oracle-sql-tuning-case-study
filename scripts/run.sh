#!/usr/bin/env bash
# One-shot run on Linux/macOS: starts Oracle 23ai Free, loads data, runs the benchmark, builds the charts.
# Requirements: Docker (or Podman with docker compose) and Python 3.10+.
# Usage, from the repository root:  bash scripts/run.sh
set -euo pipefail

docker compose up -d
echo "Waiting for Oracle to be healthy (first start: 1-2 minutes)..."
container=$(docker compose ps -q oracle)
until [ "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = "healthy" ]; do
  sleep 5
  echo "  status: $(docker inspect --format '{{.State.Health.Status}}' "$container")"
done

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet -r bench/requirements.txt
.venv/bin/python bench/bench.py --setup --system-password ChangeMe_123
.venv/bin/python bench/charts.py

echo "Done. Results in results/ and the cover image in docs/cover.png"
