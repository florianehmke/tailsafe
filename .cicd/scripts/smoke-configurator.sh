#!/usr/bin/env bash
set -euo pipefail
rm -rf .tmp/generated
mkdir -p .tmp/generated
docker build -t tailsafe-configurator:test -f containers/configurator/Dockerfile .
docker run --rm \
  -e TAILSAFE_SITE_CONFIG=/input/site.example.json \
  -e TAILSAFE_GENERATED_DIR=/generated \
  -e TAILSAFE_BACKUP_HTTP_USER=backup \
  -e TAILSAFE_BACKUP_HTTP_PASSWORD=backup-password \
  -e TAILSAFE_MAINT_HTTP_USER=maint \
  -e TAILSAFE_MAINT_HTTP_PASSWORD=maint-password \
  -e RESTIC_REPOSITORY_PASSWORD=repo-password \
  -v "$PWD/config:/input:ro" \
  -v "$PWD/.tmp/generated:/generated" \
  tailsafe-configurator:test
python -m json.tool .tmp/generated/backrest-config.json >/dev/null
