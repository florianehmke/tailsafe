#!/usr/bin/env bash
set -euo pipefail
docker compose --env-file env.example -f deploy/compose.example.yaml config >/dev/null
