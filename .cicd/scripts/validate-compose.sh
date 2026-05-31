#!/usr/bin/env bash
set -euo pipefail

if command -v docker >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v podman >/dev/null 2>&1; then
  compose_cmd=(podman compose)
else
  echo "docker or podman is required for validate:compose" >&2
  exit 1
fi

rm -rf .tmp/generated
mkdir -p .tmp/generated
cp env.example .tmp/compose.env
set -a
# shellcheck disable=SC1091
. ./env.example
set +a

python3 scripts/generate_runtime_assets.py \
  config/site.example.json \
  .tmp/generated/compose.endpoints.yaml \
  .tmp/generated/htpasswd-manifest.json

TAILSAFE_COMPOSE_ENV_FILE=../.tmp/compose.env \
  "${compose_cmd[@]}" \
  --env-file env.example \
  -f deploy/compose.example.yaml \
  -f .tmp/generated/compose.endpoints.yaml \
  config >/dev/null
